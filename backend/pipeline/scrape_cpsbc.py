"""CPSBC Registrant Directory scraper (v2).

Searches the CPSBC directory by last-name prefix, paginates through all
results, and extracts structured physician data. Saves incrementally so
the scrape can be resumed if interrupted.

Key features:
  - Verifies pagination: parses "Showing X of Y" to confirm all pages scraped
  - Exponential backoff with jitter on rate limits (429)
  - Reuses browser across prefixes, rotates context periodically
  - Randomizes prefix order to look less bot-like
  - Rotates User-Agent strings
  - Logs to file and stdout
  - Screenshots on error for debugging

Usage:
    cd backend
    python -m pipeline.scrape_cpsbc --fresh       # Start a clean scrape
    python -m pipeline.scrape_cpsbc --resume      # Resume from last progress
    python -m pipeline.scrape_cpsbc --verify      # Check for truncated prefixes
    python -m pipeline.scrape_cpsbc --prefixes A,B  # Scrape specific prefixes
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("ERROR: playwright is required. Run: pip install playwright && python -m playwright install chromium")
    sys.exit(1)


# ── Paths ──────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
OUTPUT_PATH = DATA_DIR / "cpsbc_registrants.json"
PROGRESS_PATH = DATA_DIR / "cpsbc_registrants.progress.json"
LOG_PATH = DATA_DIR / "scrape_cpsbc.log"
SCREENSHOT_DIR = DATA_DIR / "scrape_errors"

BASE_URL = "https://www.cpsbc.ca/public/registrant-directory"

# ── User-Agent rotation pool ──────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:132.0) Gecko/20100101 Firefox/132.0",
]

# ── Timing ─────────────────────────────────────────────────────────────
PAGE_DELAY_MIN = 12.0       # between pages within a prefix
PAGE_DELAY_MAX = 25.0
PREFIX_DELAY_MIN = 45.0     # between prefixes
PREFIX_DELAY_MAX = 90.0
CONTEXT_ROTATE_EVERY = 15   # rotate browser every N prefixes

# ── Rate-limit backoff ─────────────────────────────────────────────────
BACKOFF_BASE = 300.0        # 5 minutes
BACKOFF_MAX = 2700.0        # 45 minutes
MAX_RETRIES = 5             # per prefix
MAX_CONSECUTIVE_429 = 3     # stop scraper after this many in a row

# ── Logging ────────────────────────────────────────────────────────────
log = logging.getLogger("cpsbc_scraper")


def setup_logging():
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")

    fh = logging.FileHandler(LOG_PATH, mode="a")
    fh.setFormatter(fmt)
    fh.setLevel(logging.DEBUG)

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    sh.setLevel(logging.INFO)

    log.setLevel(logging.DEBUG)
    log.addHandler(fh)
    log.addHandler(sh)

    log.info("=" * 60)
    log.info(f"Scraper started at {datetime.now().isoformat()}")


# ── Helpers ─────────────────────────────────────────────────────────────

def _polite_sleep(min_s: float, max_s: float):
    delay = random.uniform(min_s, max_s)
    log.debug(f"  sleeping {delay:.1f}s")
    time.sleep(delay)


def _backoff_sleep(attempt: int):
    """Exponential backoff with jitter."""
    base = min(BACKOFF_BASE * (2 ** attempt), BACKOFF_MAX)
    jitter = random.uniform(0, base * 0.3)
    delay = base + jitter
    log.warning(f"  backoff attempt {attempt+1}: sleeping {delay:.0f}s")
    time.sleep(delay)


def _save_screenshot(page, label: str):
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = SCREENSHOT_DIR / f"{label}_{ts}.png"
    try:
        page.screenshot(path=str(path))
        log.debug(f"  screenshot saved: {path}")
    except Exception:
        pass


def _get_result_count(page) -> int | None:
    """Parse 'Showing X of Y results' header to get total count."""
    text = page.evaluate("""
        () => {
            const body = document.body.innerText;
            return body.substring(0, 2000);
        }
    """)
    m = re.search(r"of\s+([\d,]+)\s+results?", text, re.IGNORECASE)
    if m:
        return int(m.group(1).replace(",", ""))
    m = re.search(r"([\d,]+)\s+results?\s+found", text, re.IGNORECASE)
    if m:
        return int(m.group(1).replace(",", ""))
    m = re.search(r"Showing\s+\d+\s*[-–]\s*(\d+)\s+results?", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def _check_rate_limited(page) -> bool:
    """Check if the current page is a rate-limit response."""
    try:
        title = page.title().lower()
        if "429" in title or "rate" in title or "too many" in title:
            return True
        body_start = page.evaluate("() => document.body?.innerText?.substring(0, 500) || ''")
        if any(phrase in body_start.lower() for phrase in
               ["too many requests", "rate limit", "try again later"]):
            return True
    except Exception:
        pass
    return False


# ── Card parsing ───────────────────────────────────────────────────────

def _parse_result_cards(page) -> list[dict]:
    """Extract structured data from all result cards on the current page."""
    raw_cards = page.evaluate("""
        () => {
            const links = document.querySelectorAll('a[href*="registrant-directory/search-result/"]');
            const seen = new Set();
            const cards = [];
            for (const link of links) {
                const m = link.href.match(/\\/(\\d+)\\//);
                if (!m) continue;
                const id = m[1];
                if (seen.has(id)) continue;
                seen.add(id);

                const name = link.innerText.replace('arrow_forward', '').trim();

                let container = link;
                for (let i = 0; i < 10; i++) {
                    container = container.parentElement;
                    if (!container) break;
                    const t = container.innerText || '';
                    if (t.includes('Licence status') || t.includes('Practice type') || t.includes('MSP')) {
                        break;
                    }
                }

                const text = container ? container.innerText : '';
                cards.push({ id, name, text });
            }
            return cards;
        }
    """)

    results = []
    for card in raw_cards:
        text = card["text"]
        cpsbc_id = card["id"]
        full_name = card["name"]

        msp_match = re.search(r"MSP\s+([A-Z]?\d+)", text)
        status_match = re.search(r"Licence status:\s*(.+?)(?:\n|$)", text)
        class_match = re.search(r"Licence class:\s*(.+?)(?:\n|$)", text)
        practice_match = re.search(r"Practice type:\s*(.+?)(?:\n|$)", text)

        addr_match = re.search(
            r"Address:\s*\n?([\s\S]*?)(?=Licence|Practice type|NEXT|RESULTS|$)", text
        )
        address = None
        city = None
        if addr_match:
            addr_raw = addr_match.group(1).strip()
            addr_lines = [l.strip() for l in addr_raw.split("\n") if l.strip()]
            address = ", ".join(addr_lines)
            city_match = re.search(r",\s*([A-Za-z][A-Za-z .'-]+),\s*BC", address, re.IGNORECASE)
            if city_match:
                city = city_match.group(1).strip()

        practice_type = practice_match.group(1).strip() if practice_match else None
        specialty = None
        if practice_type:
            spec_match = re.search(r"(?:Specialty practice|specialist)\s*[-–]\s*(.+)",
                                   practice_type, re.IGNORECASE)
            if spec_match:
                specialty = spec_match.group(1).strip()
            elif "family" in practice_type.lower():
                specialty = "Family Medicine"

        results.append({
            "cpsbc_id": cpsbc_id,
            "full_name": full_name,
            "msp_number": msp_match.group(1) if msp_match else None,
            "licence_status": status_match.group(1).strip() if status_match else None,
            "licence_class": class_match.group(1).strip() if class_match else None,
            "practice_type": practice_type,
            "specialty": specialty,
            "address": address,
            "city": city,
        })

    return results


def _click_next_page(page) -> bool:
    """Click the NEXT PAGE link if it exists."""
    return page.evaluate("""
        () => {
            const next = Array.from(document.querySelectorAll('a')).find(
                a => a.innerText.trim().toUpperCase() === 'NEXT PAGE'
            );
            if (next) { next.click(); return true; }
            return false;
        }
    """)


# ── Per-prefix scraping ────────────────────────────────────────────────

class RateLimited(Exception):
    pass


def scrape_prefix(prefix: str, browser) -> tuple[list[dict], int | None]:
    """Scrape all results for a given last-name prefix.

    Returns (results, expected_count).
    Raises RateLimited if the site returns a 429.
    """
    results = []
    expected_count = None
    ua = random.choice(USER_AGENTS)
    context = browser.new_context(user_agent=ua)
    page = context.new_page()

    try:
        resp = page.goto(BASE_URL, wait_until="networkidle", timeout=45000)
        if resp and resp.status == 429:
            _save_screenshot(page, f"429_load_{prefix}")
            raise RateLimited("429 on initial page load")

        if _check_rate_limited(page):
            _save_screenshot(page, f"429_body_{prefix}")
            raise RateLimited("Rate limit detected in page body")

        page.fill('input[name="ps_last_name"]', prefix)
        page.click('#edit-ps-submit')
        page.wait_for_timeout(5000)

        if _check_rate_limited(page):
            _save_screenshot(page, f"429_results_{prefix}")
            raise RateLimited("Rate limit after search submit")

        expected_count = _get_result_count(page)
        if expected_count is not None:
            log.info(f"[{prefix}] expected results: {expected_count}")

        page_num = 1
        while True:
            cards = _parse_result_cards(page)
            if not cards:
                break

            results.extend(cards)
            log.info(f"[{prefix}] page {page_num}: {len(cards)} cards (total: {len(results)})")

            _polite_sleep(PAGE_DELAY_MIN, PAGE_DELAY_MAX)

            if not _click_next_page(page):
                break

            page.wait_for_timeout(5000)

            if _check_rate_limited(page):
                _save_screenshot(page, f"429_page{page_num}_{prefix}")
                log.warning(f"[{prefix}] rate limited mid-pagination at page {page_num}")
                raise RateLimited(f"Rate limit on page {page_num+1}")

            page_num += 1

    except RateLimited:
        raise
    except PlaywrightTimeout as e:
        _save_screenshot(page, f"timeout_{prefix}")
        log.warning(f"[{prefix}] timeout: {e}")
        raise RateLimited(f"Timeout (likely rate limited): {e}")
    except Exception as e:
        _save_screenshot(page, f"error_{prefix}")
        log.error(f"[{prefix}] unexpected error: {e}")
    finally:
        context.close()

    return results, expected_count


# ── Progress & persistence ─────────────────────────────────────────────

def load_progress() -> dict:
    if PROGRESS_PATH.exists():
        with open(PROGRESS_PATH) as f:
            return json.load(f)
    return {"completed_prefixes": {}, "total_registrants": 0}


def save_progress(progress: dict):
    with open(PROGRESS_PATH, "w") as f:
        json.dump(progress, f, indent=2)


def load_existing_results() -> list[dict]:
    if OUTPUT_PATH.exists():
        with open(OUTPUT_PATH) as f:
            return json.load(f)
    return []


def save_results(results: list[dict]):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)


def deduplicate(results: list[dict]) -> list[dict]:
    seen = set()
    deduped = []
    for r in results:
        key = r.get("cpsbc_id")
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        deduped.append(r)
    return deduped


def generate_prefixes() -> list[str]:
    return [
        chr(a) + chr(b)
        for a in range(ord('A'), ord('Z') + 1)
        for b in range(ord('a'), ord('z') + 1)
    ]


# ── Verify mode ────────────────────────────────────────────────────────

def verify_scrape():
    """Check existing scrape for truncated prefixes."""
    progress = load_progress()
    completed = progress.get("completed_prefixes", {})
    results = load_existing_results()

    if not completed:
        print("No progress data found. Run a scrape first.")
        return

    from collections import Counter
    actual_counts = Counter()
    for r in results:
        name = r.get("full_name", "")
        if len(name) >= 2:
            actual_counts[name[:2].title()] += 1

    print(f"{'Prefix':<8} {'Expected':>10} {'Actual':>10} {'Status':<15}")
    print("-" * 48)

    issues = 0
    for prefix, info in sorted(completed.items()):
        expected = info.get("expected_count")
        actual = actual_counts.get(prefix, 0)

        if expected is None:
            status = "no header"
        elif actual < expected:
            status = f"TRUNCATED (-{expected - actual})"
            issues += 1
        elif actual == expected:
            status = "OK"
        else:
            status = f"extra (+{actual - expected})"

        exp_str = str(expected) if expected is not None else "?"
        print(f"{prefix:<8} {exp_str:>10} {actual:>10} {status:<15}")

    all_prefixes = set(generate_prefixes())
    not_scraped = all_prefixes - set(completed.keys())
    print(f"\nTotal completed: {len(completed)}")
    print(f"Not scraped: {len(not_scraped)} prefixes")
    print(f"Issues found: {issues}")


# ── Main ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Scrape CPSBC registrant directory")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from last progress (keep existing data)")
    parser.add_argument("--fresh", action="store_true",
                        help="Start a completely clean scrape (wipes old data)")
    parser.add_argument("--verify", action="store_true",
                        help="Verify existing scrape for truncated prefixes")
    parser.add_argument("--prefixes", type=str,
                        help="Comma-separated prefixes to scrape (e.g. A,Ba,Ch)")
    args = parser.parse_args()

    setup_logging()

    if args.verify:
        verify_scrape()
        return

    # Determine prefixes
    all_prefixes = generate_prefixes()

    if args.prefixes:
        prefixes = []
        for p in args.prefixes.split(","):
            p = p.strip()
            if len(p) == 1:
                prefixes.extend([p.upper() + chr(b) for b in range(ord('a'), ord('z') + 1)])
            else:
                prefixes.append(p[0].upper() + p[1:].lower())
    else:
        prefixes = all_prefixes

    # Load or reset state
    if args.fresh:
        log.info("Starting fresh scrape — wiping old data")
        progress = {"completed_prefixes": {}, "total_registrants": 0}
        all_results = []
        save_progress(progress)
        save_results(all_results)
    elif args.resume:
        progress = load_progress()
        all_results = load_existing_results()
        if isinstance(progress.get("completed_prefixes"), list):
            log.info("Migrating old progress format (list -> dict)")
            progress["completed_prefixes"] = {
                p: {"expected_count": None, "actual_count": None}
                for p in progress["completed_prefixes"]
            }
        log.info(f"Resuming with {len(all_results):,} existing results, "
                 f"{len(progress['completed_prefixes'])} prefixes done")
    else:
        print("Specify --fresh to start clean, or --resume to continue.")
        print("Use --verify to check existing scrape quality.")
        return

    # Filter to remaining prefixes
    completed_set = set(progress["completed_prefixes"].keys())
    remaining = [p for p in prefixes if p not in completed_set]

    if not remaining:
        log.info("All prefixes already scraped.")
        return

    # Randomize order to look less bot-like
    random.shuffle(remaining)

    log.info(f"Prefixes remaining: {len(remaining)}")
    log.info(f"Page delay: {PAGE_DELAY_MIN}-{PAGE_DELAY_MAX}s")
    log.info(f"Prefix delay: {PREFIX_DELAY_MIN}-{PREFIX_DELAY_MAX}s")

    consecutive_429 = 0
    prefixes_since_rotate = 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)

        try:
            for i, prefix in enumerate(remaining):
                log.info(f"[{prefix}] prefix {i+1}/{len(remaining)}")

                # Rotate browser periodically
                prefixes_since_rotate += 1
                if prefixes_since_rotate >= CONTEXT_ROTATE_EVERY:
                    log.info("  rotating browser")
                    browser.close()
                    _polite_sleep(10, 20)
                    browser = pw.chromium.launch(headless=True)
                    prefixes_since_rotate = 0

                # Retry loop with exponential backoff
                results = []
                expected_count = None
                success = False

                for attempt in range(MAX_RETRIES):
                    try:
                        results, expected_count = scrape_prefix(prefix, browser)
                        success = True
                        break
                    except RateLimited as e:
                        log.warning(f"[{prefix}] rate limited: {e}")
                        if attempt < MAX_RETRIES - 1:
                            _backoff_sleep(attempt)
                            browser.close()
                            browser = pw.chromium.launch(headless=True)
                            prefixes_since_rotate = 0
                        else:
                            log.error(f"[{prefix}] giving up after {MAX_RETRIES} attempts")

                if not success:
                    consecutive_429 += 1
                    if consecutive_429 >= MAX_CONSECUTIVE_429:
                        log.error(f"{MAX_CONSECUTIVE_429} consecutive rate-limit failures. "
                                  "Resume later with: --resume")
                        break
                    continue
                else:
                    consecutive_429 = 0

                # Verify pagination completeness
                actual_count = len(results)
                if expected_count is not None and actual_count < expected_count:
                    log.warning(f"[{prefix}] PAGINATION TRUNCATED: "
                                f"expected {expected_count}, got {actual_count}")

                # Save incrementally
                all_results.extend(results)
                progress["completed_prefixes"][prefix] = {
                    "expected_count": expected_count,
                    "actual_count": actual_count,
                    "scraped_at": datetime.now().isoformat(),
                }
                progress["total_registrants"] = len(all_results)

                save_results(deduplicate(all_results))
                save_progress(progress)

                log.info(f"[{prefix}] done: {actual_count} registrants "
                         f"(cumulative: {len(all_results):,})")

                # Pause between prefixes
                if i < len(remaining) - 1:
                    _polite_sleep(PREFIX_DELAY_MIN, PREFIX_DELAY_MAX)

        finally:
            browser.close()

    # Final dedup and save
    deduped = deduplicate(all_results)
    save_results(deduped)

    log.info(f"\nScrape complete.")
    log.info(f"  Total registrants: {len(deduped):,} (deduped from {len(all_results):,})")
    log.info(f"  Output: {OUTPUT_PATH}")

    with_specialty = sum(1 for r in deduped if r.get("specialty"))
    with_city = sum(1 for r in deduped if r.get("city"))
    practising = sum(1 for r in deduped if (r.get("licence_status") or "").lower() == "practising")
    log.info(f"  With specialty: {with_specialty:,}")
    log.info(f"  With city: {with_city:,}")
    log.info(f"  Practising: {practising:,}")


if __name__ == "__main__":
    main()
