"""Aggregation engine with k-anonymity and dominance suppression."""

from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Any

from app.privacy import apply_k_anonymity, apply_dominance_suppression


def compute_aggregations(
    records: list[dict[str, Any]],
    geo_level: str = "city",
    geo_key: str = "city",
) -> list[dict[str, Any]]:
    """Group billing records by geography and compute summary statistics.

    *records* should be dicts with at least:
    - ``fiscal_year``, ``geo_key`` (city/ha/facility), ``amount_gross``

    Returns aggregated cells with privacy suppression applied.
    """
    # Group by (fiscal_year, geo_id, specialty_group)
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in records:
        key = (
            r.get("fiscal_year", ""),
            r.get(geo_key, "Unknown"),
            r.get("specialty_group", "All"),
        )
        groups[key].append(r)

    agg_cells = []
    for (year, geo_id, spec), members in groups.items():
        amounts = [m["amount_gross"] for m in members if m.get("amount_gross") is not None]
        n_phys = len(set(m.get("entity_key_hash", id(m)) for m in members))

        # Dominance: share of top contributor
        max_share = 0.0
        total = sum(amounts)
        if total > 0 and amounts:
            max_share = max(amounts) / total

        cell = {
            "fiscal_year": year,
            "geo_level": geo_level,
            "geo_id": geo_id,
            "geo_name": geo_id,
            "specialty_group": spec,
            "n_physicians": n_phys,
            "total_payments": round(total, 2),
            "median_payments": round(statistics.median(amounts), 2) if amounts else None,
            "pct_change_yoy": None,  # computed in a second pass
            "suppressed": False,
            "suppression_reason": None,
            "max_share": max_share,
        }
        agg_cells.append(cell)

    # Apply privacy rules
    agg_cells = apply_k_anonymity(agg_cells)
    agg_cells = apply_dominance_suppression(agg_cells)

    # Remove internal-only fields
    for cell in agg_cells:
        cell.pop("max_share", None)

    return agg_cells


def compute_yoy(
    current: list[dict[str, Any]],
    previous: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Add ``pct_change_yoy`` to *current* cells by matching with *previous* cells.

    Only cells that are k-safe in *both* years get a YoY value.
    """
    prev_lookup = {}
    for cell in previous:
        key = (cell["geo_level"], cell["geo_id"], cell.get("specialty_group", "All"))
        if not cell.get("suppressed"):
            prev_lookup[key] = cell

    result = []
    for cell in current:
        cell = dict(cell)
        key = (cell["geo_level"], cell["geo_id"], cell.get("specialty_group", "All"))
        prev_cell = prev_lookup.get(key)
        if (
            prev_cell
            and not cell.get("suppressed")
            and prev_cell.get("total_payments")
            and prev_cell["total_payments"] > 0
            and cell.get("total_payments")
        ):
            cell["pct_change_yoy"] = round(
                (cell["total_payments"] - prev_cell["total_payments"]) / prev_cell["total_payments"],
                4,
            )
        result.append(cell)
    return result
