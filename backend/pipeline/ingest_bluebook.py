"""MSP Blue Book PDF parser.

Downloads and parses the annual MSP Payment Information publications
(commonly called the *Blue Book*) into structured records.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

try:
    import pdfplumber
except ImportError:  # pragma: no cover
    pdfplumber = None  # type: ignore[assignment]


def parse_bluebook_pdf(path: str | Path) -> list[dict[str, Any]]:
    """Extract physician billing rows from a Blue Book PDF.

    Each row is expected to contain at minimum:
    - payee_name (string)
    - amount_gross (float)
    - category / specialty info (string, optional)

    Returns a list of dicts suitable for loading into ``payments_raw``.
    """
    if pdfplumber is None:
        raise ImportError("pdfplumber is required for PDF parsing – pip install pdfplumber")

    results: list[dict[str, Any]] = []
    path = Path(path)

    with pdfplumber.open(path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if row is None or len(row) < 2:
                        continue
                    record = _parse_row(row, page_num)
                    if record:
                        results.append(record)
    return results


# Currency regex: "$1,234,567.89" or "1234567.89"
_CURRENCY_RE = re.compile(r"\$?\s*([\d,]+(?:\.\d{2})?)")


def _parse_row(row: list[str | None], page_num: int) -> dict[str, Any] | None:
    """Attempt to parse a single table row into a billing record."""
    # Skip header/footer rows
    cells = [c.strip() if c else "" for c in row]
    if not cells[0] or cells[0].upper().startswith(("PAYEE", "NAME", "PAGE", "TOTAL")):
        return None

    name = cells[0]
    # Find the first currency-like cell
    amount = None
    for cell in cells[1:]:
        m = _CURRENCY_RE.search(cell)
        if m:
            amount = float(m.group(1).replace(",", ""))
            break

    if amount is None:
        return None

    category = cells[1] if len(cells) > 2 else ""

    return {
        "payee_name": name,
        "amount_gross": amount,
        "category": category,
        "source_page": page_num,
    }


def extract_fiscal_year(filename: str) -> str | None:
    """Guess the fiscal year from a Blue Book filename.

    Examples:
        ``"bluebook-2022-2023.pdf"`` → ``"2022-2023"``
    """
    m = re.search(r"(\d{4})[_-](\d{4})", filename)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    return None
