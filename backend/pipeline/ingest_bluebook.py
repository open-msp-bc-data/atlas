"""MSP Blue Book PDF parser.

Parses the annual MSP Payment Information publications (the "Blue Book")
into structured records. The PDFs use a 3-column text layout with
dot-leaders separating names from amounts:

    Surname, Given Names .......................... 123,456.78

Some names wrap across lines when they are long. The parser handles
wrapped names by detecting continuation lines (lines that start with
a name fragment followed by dots+amount but have no preceding amount
on the same logical entry).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

try:
    import pdfplumber
except ImportError:  # pragma: no cover
    pdfplumber = None  # type: ignore[assignment]


# Matches "Name .... 123,456.78" pattern. The name part may contain
# letters, spaces, hyphens, apostrophes, periods, commas, and parens.
# The dots act as a visual separator. The amount has no $ sign in the text.
_ENTRY_RE = re.compile(
    r"([A-Za-z][A-Za-z \-'.,()]+?)"  # name (starts with letter)
    r"\s*\.{2,}\s*"                    # dot-leader (2+ dots)
    r"([\d,]+\.\d{2})"                # amount (digits with commas, 2 decimal places)
)

def parse_bluebook_pdf(path: str | Path) -> list[dict[str, Any]]:
    """Extract physician/org billing rows from a Blue Book PDF.

    Returns a list of dicts with keys:
    - payee_name: str
    - amount_gross: float
    - section: str ("practitioners", "organizations", or "other")
    - source_page: int
    - fiscal_year: str or None
    """
    if pdfplumber is None:
        raise ImportError("pdfplumber is required – pip install pdfplumber")

    path = Path(path)
    fiscal_year = extract_fiscal_year(path.name)
    results: list[dict[str, Any]] = []
    current_section = "practitioners"

    with pdfplumber.open(path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                continue

            # Skip non-data pages (intro, notes, table of contents)
            is_data_page = bool(_ENTRY_RE.search(text))

            # Detect section changes by looking for headers on their own
            # lines (not embedded in paragraph text). Some pages have intro
            # paragraphs that mention all three sections in running text,
            # which would cause false section switches.
            if is_data_page:
                for line in text.split("\n"):
                    line_stripped = line.strip().upper()
                    if line_stripped.startswith("PAYMENTS TO PRACTITIONERS"):
                        current_section = "practitioners"
                    elif line_stripped.startswith("PAYMENTS TO ORGANIZATIONS"):
                        current_section = "organizations"
                    elif line_stripped.startswith("PAYMENTS TO HEALTH"):
                        current_section = "organizations"
                    elif line_stripped.startswith("OTHER ACCOUNTS"):
                        current_section = "other"

            if not is_data_page:
                continue

            # Extract all name-amount pairs from the page text
            for match in _ENTRY_RE.finditer(text):
                name = _clean_name(match.group(1))
                amount_str = match.group(2).replace(",", "")

                if not name or len(name) < 2:
                    continue

                try:
                    amount = float(amount_str)
                except ValueError:
                    continue

                # Sanity check: no single payment should exceed $50M
                if amount > 50_000_000:
                    continue

                results.append({
                    "payee_name": name,
                    "amount_gross": amount,
                    "section": current_section,
                    "source_page": page_num,
                    "fiscal_year": fiscal_year,
                })

    return results


def _clean_name(raw: str) -> str:
    """Normalize a payee name extracted from the PDF."""
    name = raw.strip().rstrip(".")
    # Collapse multiple spaces
    name = re.sub(r"\s+", " ", name)
    # Strip trailing commas or dots
    name = name.strip(" ,.")
    return name


def extract_fiscal_year(filename: str) -> str | None:
    """Guess the fiscal year from a Blue Book filename.

    Handles multiple naming conventions:
        "bluebook_2023-24.pdf"    → "2023-2024"
        "blue-book-2018-19.pdf"   → "2018-2019"
        "bluebook2012.pdf"        → "2011-2012"
        "bluebook_2020_21_final.pdf" → "2020-2021"
    """
    # Try 4-digit + 4-digit: "2022-2023"
    m = re.search(r"(\d{4})[_-](\d{4})", filename)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    # Try 4-digit + 2-digit: "2023-24" or "2020_21"
    m = re.search(r"(\d{4})[_-](\d{2})", filename)
    if m:
        start = int(m.group(1))
        end_short = int(m.group(2))
        century = start // 100 * 100
        return f"{start}-{century + end_short}"

    # Try single 4-digit year: "bluebook2012" (fiscal year ending March 31)
    m = re.search(r"(\d{4})", filename)
    if m:
        end_year = int(m.group(1))
        return f"{end_year - 1}-{end_year}"

    return None
