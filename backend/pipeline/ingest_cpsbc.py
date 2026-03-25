"""CPSBC Registrant Directory scraper (stub).

This module provides the interface for scraping the College of Physicians
and Surgeons of British Columbia public registrant directory.

NOTE: Actual scraping is disabled by default to respect the site's ToS.
Use ``--live`` flag or set ``CPSBC_LIVE=1`` to enable real HTTP requests.
The default mode reads from a cached JSON snapshot.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def scrape_cpsbc_directory(
    output_path: str | Path = "data/raw/cpsbc_snapshot.json",
    live: bool = False,
) -> list[dict[str, Any]]:
    """Scrape or load CPSBC registrant data.

    Returns a list of practitioner dicts with fields:
    - full_name, specialty, city, license_status, cpsbc_id
    """
    if live:
        return _scrape_live(output_path)
    return _load_snapshot(output_path)


def _load_snapshot(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    with open(p) as fh:
        return json.load(fh)


def _scrape_live(output_path: str | Path) -> list[dict[str, Any]]:
    """Placeholder for live scraping logic.

    A real implementation would:
    1. Paginate through https://www.cpsbc.ca/public/registrant-directory
    2. Extract full_name, specialty, city, license_status, cpsbc_id
    3. Handle retries and rate-limiting
    4. Save snapshot to *output_path*
    """
    raise NotImplementedError(
        "Live CPSBC scraping is not yet implemented. "
        "Please provide a snapshot JSON file at the expected path."
    )
