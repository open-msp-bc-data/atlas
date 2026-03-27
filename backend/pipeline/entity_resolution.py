"""Entity resolution – fuzzy matching of payee names to CPSBC registrants."""

from __future__ import annotations

import hashlib
from typing import Any

from rapidfuzz import fuzz, process


def normalize_name(name: str) -> str:
    """Lowercase, strip titles and punctuation, collapse whitespace."""
    import re

    name = name.lower().strip()
    # Remove common titles
    for title in ("dr.", "dr ", "md", "m.d.", "frcpc", "frcsc", "ccfp"):
        name = name.replace(title, "")
    name = re.sub(r"[^\w\s]", "", name)
    return " ".join(name.split())


def build_entity_key(name: str, city: str, salt: str = "") -> str:
    """Create a salted SHA-256 hash key from normalized name + city."""
    normalized = normalize_name(name)
    city_norm = city.strip().lower() if city else ""
    payload = f"{salt}:{normalized}:{city_norm}"
    return hashlib.sha256(payload.encode()).hexdigest()


def match_payee_to_registrants(
    payee_name: str,
    registrants: list[dict[str, Any]],
    threshold: int = 90,
    city: str | None = None,
) -> dict[str, Any] | None:
    """Find the best registrant match for a payee name using fuzzy matching.

    Uses RapidFuzz ``token_set_ratio`` with optional city tie-breaking.

    Returns the matched registrant dict (with ``match_score``) or None.
    """
    if not registrants:
        return None

    # Blocking: if city is given, prefer same-city candidates first
    candidates = registrants
    if city:
        city_lower = city.strip().lower()
        same_city = [r for r in registrants if (r.get("city") or "").strip().lower() == city_lower]
        if same_city:
            candidates = same_city

    names = [r.get("full_name", "") for r in candidates]
    result = process.extractOne(
        normalize_name(payee_name),
        [normalize_name(n) for n in names],
        scorer=fuzz.token_set_ratio,
        score_cutoff=threshold,
    )
    if result is None:
        return None

    matched_text, score, idx = result
    matched = dict(candidates[idx])
    matched["match_score"] = score
    matched["match_method"] = "fuzzy"
    return matched


def resolve_entities(
    payees: list[dict[str, Any]],
    registrants: list[dict[str, Any]],
    salt: str = "",
    threshold: int = 90,
) -> list[dict[str, Any]]:
    """Run entity resolution on a list of payee records.

    Returns enriched records with ``entity_key_hash``, ``match_score``, etc.
    """
    results = []
    for payee in payees:
        name = payee.get("payee_name", "")
        city = payee.get("city")
        match = match_payee_to_registrants(name, registrants, threshold=threshold, city=city)

        record = dict(payee)
        record["entity_key_hash"] = build_entity_key(name, city or "", salt)
        if match:
            record["matched_name"] = match.get("full_name")
            record["cpsbc_id"] = match.get("cpsbc_id")
            record["match_score"] = match.get("match_score")
            record["match_method"] = match.get("match_method", "fuzzy")
            record["specialty"] = match.get("specialty")
        else:
            record["matched_name"] = None
            record["cpsbc_id"] = None
            record["match_score"] = 0
            record["match_method"] = "none"
        results.append(record)

    return results
