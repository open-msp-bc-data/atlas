"""CPSBC Registrant Directory scraper.

Searches the CPSBC directory by last-name prefix (A-Z), paginates through
all results, and extracts structured physician data. Results are saved
incrementally to a JSON file so the scrape can be resumed if interrupted.

Usage:
    cd backend
    python -m pipeline.scrape_cpsbc

    # Resume from where it left off (skips already-scraped prefixes):
    python -m pipeline.scrape_cpsbc --resume

    # Scrape only specific prefixes:
    python -m pipeline.scrape_cpsbc --prefixes A,B,C

Polite scraping: 4-6 second random delay between page requests, proper
User-Agent, and a fresh browser session per prefix to avoid long-lived
connections.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("ERROR: playwright is required. Run: pip install playwright && python -m playwright install chromium")
    sys.exit(1)


OUTPUT_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "cpsbc_registrants.json"
PROGRESS_PATH = OUTPUT_PATH.with_suffix(".progress.json")
BASE_URL = "https://www.cpsbc.ca/public/registrant-directory"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Polite delay range (seconds) between page requests
DELAY_MIN = 8.0
DELAY_MAX = 15.0

# Longer delay between letter prefixes (let the server breathe)
PREFIX_DELAY_MIN = 20.0
PREFIX_DELAY_MAX = 35.0

# Backoff delay when rate-limited (seconds)
RATE_LIMIT_BACKOFF = 300.0  # 5 minutes
MAX_CONSECUTIVE_ERRORS = 5  # stop after this many failures in a row


def _polite_sleep(min_s: float = DELAY_MIN, max_s: float = DELAY_MAX):
    """Random delay to avoid hammering the server."""
    delay = random.uniform(min_s, max_s)
    time.sleep(delay)


def _parse_result_cards(page) -> list[dict]:
    """Extract structured data from all result cards on the current page.

    Each result card is an h5 with a profile link. The sibling/adjacent
    elements contain licence status, practice type, address, etc. We walk
    from each h5 up to a shared ancestor that contains all the card data,
    then parse the innerText.
    """
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

                // Walk up from the h5 to find a container with the full card text.
                // The card structure is: div > div.ps-contact__title > div > h5 > a
                // The card data (MSP, status, address) is in sibling divs.
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

        # Address: lines after "Address:" until next labelled field or end
        addr_match = re.search(
            r"Address:\s*\n?([\s\S]*?)(?=Licence|Practice type|NEXT|RESULTS|$)", text
        )
        address = None
        city = None
        if addr_match:
            addr_raw = addr_match.group(1).strip()
            addr_lines = [l.strip() for l in addr_raw.split("\n") if l.strip()]
            address = ", ".join(addr_lines)
            # City from BC address pattern: "..., City, BC, V1X 2Y3, Canada"
            city_match = re.search(r",\s*([A-Za-z][A-Za-z .'-]+),\s*BC", address, re.IGNORECASE)
            if city_match:
                city = city_match.group(1).strip()

        practice_type = practice_match.group(1).strip() if practice_match else None
        specialty = None
        if practice_type:
            spec_match = re.search(r"(?:Specialty practice|specialist)\s*[-–]\s*(.+)", practice_type, re.IGNORECASE)
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
    """Click the NEXT PAGE link if it exists. Returns True if clicked.

    We must click within the page context (not navigate to the URL) because
    the CPSBC site uses server-side session state for search results.
    """
    clicked = page.evaluate("""
        () => {
            const next = Array.from(document.querySelectorAll('a')).find(
                a => a.innerText.trim().toUpperCase() === 'NEXT PAGE'
            );
            if (next) { next.click(); return true; }
            return false;
        }
    """)
    return clicked


def scrape_prefix(prefix: str, playwright_instance) -> list[dict]:
    """Scrape all results for a given last-name prefix."""
    results = []
    browser = playwright_instance.chromium.launch(headless=True)
    page = browser.new_page(user_agent=USER_AGENT)

    try:
        # Initial search
        resp = page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
        if resp and resp.status == 429:
            print(f"    RATE LIMITED (429) on initial load. Backing off {RATE_LIMIT_BACKOFF}s...")
            time.sleep(RATE_LIMIT_BACKOFF)
            browser.close()
            return results

        page.fill('input[name="ps_last_name"]', prefix)
        page.click('#edit-ps-submit')
        page.wait_for_timeout(5000)

        page_num = 1
        while True:
            cards = _parse_result_cards(page)
            if not cards:
                break

            results.extend(cards)
            print(f"    Page {page_num}: {len(cards)} results (total: {len(results)})")

            _polite_sleep()

            if not _click_next_page(page):
                break

            page.wait_for_timeout(5000)
            page_num += 1

    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "Timeout" in error_msg:
            print(f"    RATE LIMITED or TIMEOUT on page {page_num if 'page_num' in dir() else '?'}. Backing off...")
            time.sleep(RATE_LIMIT_BACKOFF)
        else:
            print(f"    ERROR on page {page_num if 'page_num' in dir() else '?'}: {e}")
    finally:
        browser.close()

    return results


def load_progress() -> dict:
    """Load scraping progress (which prefixes are done)."""
    if PROGRESS_PATH.exists():
        with open(PROGRESS_PATH) as f:
            return json.load(f)
    return {"completed_prefixes": [], "total_registrants": 0}


def save_progress(progress: dict):
    """Save scraping progress."""
    with open(PROGRESS_PATH, "w") as f:
        json.dump(progress, f, indent=2)


def load_existing_results() -> list[dict]:
    """Load previously scraped results."""
    if OUTPUT_PATH.exists():
        with open(OUTPUT_PATH) as f:
            return json.load(f)
    return []


def save_results(results: list[dict]):
    """Save all results to the output file."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description="Scrape CPSBC registrant directory")
    parser.add_argument("--resume", action="store_true", help="Resume from last progress")
    parser.add_argument("--prefixes", type=str, help="Comma-separated prefixes to scrape (e.g. A,B,C)")
    args = parser.parse_args()

    # Two-letter prefixes (CPSBC requires at least 2 characters)
    all_prefixes = [
        chr(a) + chr(b)
        for a in range(ord('A'), ord('Z') + 1)
        for b in range(ord('a'), ord('z') + 1)
    ]

    if args.prefixes:
        prefixes = [p.strip() for p in args.prefixes.split(",")]
        # If single letters given, expand to two-letter prefixes
        expanded = []
        for p in prefixes:
            if len(p) == 1:
                expanded.extend([p + chr(b) for b in range(ord('a'), ord('z') + 1)])
            else:
                expanded.append(p)
        prefixes = expanded
    else:
        prefixes = all_prefixes

    progress = load_progress() if args.resume else {"completed_prefixes": [], "total_registrants": 0}
    all_results = load_existing_results() if args.resume else []

    # Filter out already-completed prefixes
    remaining = [p for p in prefixes if p not in progress["completed_prefixes"]]
    if not remaining:
        print("All prefixes already scraped. Use without --resume to start fresh.")
        return

    print(f"CPSBC Directory Scraper")
    print(f"  Output: {OUTPUT_PATH}")
    print(f"  Prefixes to scrape: {', '.join(remaining)} ({len(remaining)} remaining)")
    print(f"  Delay between pages: {DELAY_MIN}-{DELAY_MAX}s")
    print(f"  Delay between prefixes: {PREFIX_DELAY_MIN}-{PREFIX_DELAY_MAX}s")
    if all_results:
        print(f"  Resuming with {len(all_results):,} existing results")
    print()

    consecutive_errors = 0

    with sync_playwright() as pw:
        for i, prefix in enumerate(remaining):
            print(f"[{prefix}] Searching prefix {i+1}/{len(remaining)}...")

            # Retry loop: back off and retry on rate limits instead of bailing
            max_retries = 3
            results = []
            for attempt in range(max_retries):
                start = time.time()
                results = scrape_prefix(prefix, pw)
                elapsed = time.time() - start

                if len(results) > 0 or elapsed < 10:
                    # Got results, or fast empty response (legitimately no matches)
                    break

                # Slow empty response = likely rate limited
                if attempt < max_retries - 1:
                    backoff = RATE_LIMIT_BACKOFF * (attempt + 1)
                    print(f"    Rate limited on '{prefix}' (attempt {attempt+1}/{max_retries}). "
                          f"Sleeping {backoff:.0f}s...")
                    time.sleep(backoff)

            # Track consecutive rate-limit failures
            was_rate_limited = len(results) == 0 and elapsed >= 10
            if was_rate_limited:
                consecutive_errors += 1
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    print(f"\n{MAX_CONSECUTIVE_ERRORS} consecutive rate-limit failures after retries.")
                    print(f"Resume later with: python -m pipeline.scrape_cpsbc --resume")
                    break
                # Don't mark rate-limited prefixes as completed
                print(f"[{prefix}] Skipped (rate limited after {max_retries} attempts)")
                continue
            else:
                consecutive_errors = 0

            all_results.extend(results)
            progress["completed_prefixes"].append(prefix)
            progress["total_registrants"] = len(all_results)

            # Save after each prefix (incremental)
            save_results(all_results)
            save_progress(progress)

            print(f"[{prefix}] Done: {len(results)} registrants in {elapsed:.0f}s "
                  f"(cumulative: {len(all_results):,})")

            # Long pause between prefixes
            if i < len(remaining) - 1:
                _polite_sleep(PREFIX_DELAY_MIN, PREFIX_DELAY_MAX)

    # Deduplicate by cpsbc_id
    seen = set()
    deduped = []
    for r in all_results:
        key = r.get("cpsbc_id")
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        deduped.append(r)

    save_results(deduped)

    print(f"\nScrape complete.")
    print(f"  Total registrants: {len(deduped):,} (deduped from {len(all_results):,})")
    print(f"  Output: {OUTPUT_PATH}")

    # Stats
    with_specialty = sum(1 for r in deduped if r.get("specialty"))
    with_city = sum(1 for r in deduped if r.get("city"))
    practising = sum(1 for r in deduped if (r.get("licence_status") or "").lower() == "practising")
    print(f"  With specialty: {with_specialty:,}")
    print(f"  With city: {with_city:,}")
    print(f"  Practising: {practising:,}")


if __name__ == "__main__":
    main()
