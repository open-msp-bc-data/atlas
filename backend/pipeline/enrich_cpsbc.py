"""CPSBC enrichment: match scraped CPSBC data to existing DB records.

Reads cpsbc_registrants.json and updates physicians_public + physicians_raw
with real specialty, city, and practice type where matches are found.

Usage:
    cd backend
    PRIVACY_SALT="your-secret" python -m pipeline.enrich_cpsbc
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rapidfuzz import fuzz
from sqlalchemy.orm import sessionmaker, Session

from app.database import init_db, get_engine
from app.models import PhysicianRaw, PhysicianPublic
from app.privacy import generalize_specialty
from pipeline.entity_resolution import normalize_name
from pipeline.geocode import BC_CITY_CENTROIDS, CITY_TO_HEALTH_AUTHORITY
from app.privacy import jitter_location

import hashlib

CPSBC_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "cpsbc_registrants.json"
MATCH_THRESHOLD = 85  # fuzzy match score


def load_cpsbc() -> list[dict]:
    if not CPSBC_PATH.exists():
        print(f"ERROR: {CPSBC_PATH} not found. Run scrape_cpsbc.py first.")
        sys.exit(1)
    with open(CPSBC_PATH) as f:
        return json.load(f)


def build_cpsbc_index(registrants: list[dict]) -> dict[str, dict]:
    """Build a normalized-name → registrant lookup.

    For duplicate names, prefer the one with more data (specialty, city).
    """
    index = {}
    for r in registrants:
        norm = normalize_name(r["full_name"])
        existing = index.get(norm)
        if existing is None:
            index[norm] = r
        else:
            # Prefer entry with more useful data
            new_score = bool(r.get("specialty")) + bool(r.get("city")) + bool(r.get("licence_status"))
            old_score = bool(existing.get("specialty")) + bool(existing.get("city")) + bool(existing.get("licence_status"))
            if new_score > old_score:
                index[norm] = r
    return index


def match_physician(name: str, cpsbc_index: dict[str, dict]) -> dict | None:
    """Try exact match first, then fuzzy match against the CPSBC index."""
    norm = normalize_name(name)

    # Exact match
    if norm in cpsbc_index:
        return cpsbc_index[norm]

    # Fuzzy match (only against names starting with same letter for speed)
    first_char = norm[0] if norm else ""
    candidates = {k: v for k, v in cpsbc_index.items() if k and k[0] == first_char}

    best_score = 0
    best_match = None
    for cpsbc_norm, reg in candidates.items():
        score = fuzz.token_set_ratio(norm, cpsbc_norm)
        if score > best_score and score >= MATCH_THRESHOLD:
            best_score = score
            best_match = reg

    return best_match


def run():
    print("Loading CPSBC data...")
    registrants = load_cpsbc()
    print(f"  {len(registrants):,} registrants loaded")

    cpsbc_index = build_cpsbc_index(registrants)
    print(f"  {len(cpsbc_index):,} unique normalized names")

    init_db()
    engine = get_engine()
    SessionLocal = sessionmaker(bind=engine)
    db: Session = SessionLocal()

    # Load all physicians
    raw_records = db.query(PhysicianRaw).all()
    print(f"  {len(raw_records):,} physicians in database")

    matched = 0
    enriched_specialty = 0
    enriched_city = 0

    for i, raw in enumerate(raw_records):
        match = match_physician(raw.full_name, cpsbc_index)
        if not match:
            continue

        matched += 1
        with db.no_autoflush:
            pub = db.query(PhysicianPublic).filter(
                PhysicianPublic.physician_id == raw.id
            ).first()
        if not pub:
            continue

        # Update specialty if we have it and it's currently unknown
        cpsbc_specialty = match.get("specialty")
        if cpsbc_specialty and (not raw.specialty or pub.specialty_group == "Unknown"):
            raw.specialty = cpsbc_specialty
            pub.specialty = cpsbc_specialty
            pub.specialty_group = generalize_specialty(cpsbc_specialty)
            enriched_specialty += 1

        # Update city if CPSBC has it and current city is hash-assigned
        cpsbc_city = match.get("city")
        if cpsbc_city:
            city_lower = cpsbc_city.strip().lower()
            if city_lower in BC_CITY_CENTROIDS:
                lat, lng = BC_CITY_CENTROIDS[city_lower]
                ha = CITY_TO_HEALTH_AUTHORITY.get(city_lower, raw.health_authority)

                raw.city = cpsbc_city.title()
                raw.health_authority = ha
                raw.lat = lat
                raw.lng = lng

                stable_seed = int(hashlib.sha256(normalize_name(raw.full_name).encode()).hexdigest()[:8], 16)
                lat_approx, lng_approx = jitter_location(lat, lng, seed=stable_seed)

                pub.city = cpsbc_city.title()
                pub.health_authority = ha
                pub.lat_approx = lat_approx
                pub.lng_approx = lng_approx
                enriched_city += 1

        # Update practice type / license info on raw record
        if match.get("licence_status"):
            raw.license_status = match["licence_status"]
        if match.get("cpsbc_id") and not raw.cpsbc_id:
            # Only set if not already claimed by another physician (unique constraint)
            existing = db.query(PhysicianRaw).filter(
                PhysicianRaw.cpsbc_id == match["cpsbc_id"],
                PhysicianRaw.id != raw.id,
            ).first()
            if not existing:
                raw.cpsbc_id = match["cpsbc_id"]

        if (i + 1) % 5000 == 0:
            db.commit()
            print(f"  {i+1:,} / {len(raw_records):,}...")

    db.commit()
    db.close()

    print(f"\nEnrichment complete.")
    print(f"  Matched: {matched:,} / {len(raw_records):,} ({matched*100//len(raw_records)}%)")
    print(f"  Specialty enriched: {enriched_specialty:,}")
    print(f"  City enriched: {enriched_city:,}")


if __name__ == "__main__":
    run()
