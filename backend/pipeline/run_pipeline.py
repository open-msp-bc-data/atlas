"""End-to-end pipeline: parse Blue Book PDFs → deduplicate → anonymise → load DB.

Usage:
    cd backend
    PRIVACY_SALT="your-secret" python -m pipeline.run_pipeline

Without CPSBC registrant data, physicians are geocoded to random BC cities
using a hash-based assignment. Specialties are unknown until CPSBC data is
available.
"""

from __future__ import annotations

import glob
import hashlib
import os
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import init_db, get_engine
from app.models import PhysicianRaw, Billing, PhysicianPublic, Aggregation
from app.privacy import deterministic_pseudo_id, jitter_location
from pipeline.ingest_bluebook import parse_bluebook_pdf
from pipeline.geocode import BC_CITY_CENTROIDS, CITY_TO_HEALTH_AUTHORITY
from pipeline.entity_resolution import normalize_name

from sqlalchemy.orm import sessionmaker, Session


# Use city centroids as geocoding targets (no street addresses in Blue Book)
_CITIES = list(BC_CITY_CENTROIDS.keys())


def _assign_city(name: str) -> str:
    """Deterministically assign a BC city based on name hash.

    This is a placeholder until CPSBC data provides real practice cities.
    The assignment is stable (same name always gets same city) so the map
    is consistent across runs, but the cities are NOT real.
    """
    h = int(hashlib.sha256(normalize_name(name).encode()).hexdigest()[:8], 16)
    return _CITIES[h % len(_CITIES)]


def run(data_dir: str = "../data/raw", years: list[str] | None = None):
    """Parse all Blue Book PDFs and load into the database."""
    salt = os.environ.get("PRIVACY_SALT", "")
    if not salt or salt == "CHANGE_ME_IN_PRODUCTION":
        print("ERROR: Set PRIVACY_SALT env var before running the pipeline.")
        sys.exit(1)

    init_db()
    engine = get_engine()
    SessionLocal = sessionmaker(bind=engine)
    db: Session = SessionLocal()

    # Clear existing data
    print("Clearing existing data...")
    db.query(Aggregation).delete()
    db.query(PhysicianPublic).delete()
    db.query(Billing).delete()
    db.query(PhysicianRaw).delete()
    db.commit()

    # ── Stage 1: Parse all PDFs ──────────────────────────────────────
    pdfs = sorted(glob.glob(os.path.join(data_dir, "bluebook_*.pdf")))
    if not pdfs:
        pdfs = sorted(glob.glob(os.path.join(data_dir, "blue-book-*.pdf")))
    if not pdfs:
        print(f"ERROR: No Blue Book PDFs found in {data_dir}")
        sys.exit(1)

    all_rows: list[dict] = []
    for pdf_path in pdfs:
        print(f"  Parsing {os.path.basename(pdf_path)}...", end=" ", flush=True)
        rows = parse_bluebook_pdf(pdf_path)
        practitioners = [r for r in rows if r["section"] == "practitioners"]
        print(f"{len(practitioners):,} practitioners")
        all_rows.extend(practitioners)

        if years and rows:
            fy = rows[0].get("fiscal_year")
            if fy and fy not in years:
                continue

    print(f"\nTotal practitioner rows: {len(all_rows):,}")

    # ── Stage 2: Deduplicate names → unique physicians ───────────────
    # Group by normalized name to identify unique physicians across years
    physician_map: dict[str, dict] = {}  # normalized_name → physician info
    billings_by_name: dict[str, list[dict]] = defaultdict(list)

    for row in all_rows:
        norm = normalize_name(row["payee_name"])
        if norm not in physician_map:
            city = _assign_city(row["payee_name"])
            physician_map[norm] = {
                "payee_name": row["payee_name"],
                "normalized": norm,
                "city": city,
                "health_authority": CITY_TO_HEALTH_AUTHORITY.get(city, "Unknown"),
            }
        billings_by_name[norm].append({
            "year": row["fiscal_year"],
            "amount": row["amount_gross"],
        })

    print(f"Unique physicians: {len(physician_map):,}")

    # ── Stage 3: Write to database ───────────────────────────────────
    print("Writing to database...")
    physician_ids: dict[str, int] = {}  # normalized_name → db id

    for i, (norm, info) in enumerate(physician_map.items()):
        city = info["city"]
        lat, lng = BC_CITY_CENTROIDS.get(city, (49.28, -123.12))

        # Raw record (no real address available from Blue Book)
        raw = PhysicianRaw(
            full_name=info["payee_name"],
            specialty=None,  # Unknown without CPSBC data
            address=None,
            city=city.title(),
            health_authority=info["health_authority"],
            lat=lat,
            lng=lng,
            license_status=None,
            cpsbc_id=None,
        )
        db.add(raw)
        db.flush()
        physician_ids[norm] = raw.id

        # Public record (anonymised)
        pseudo = deterministic_pseudo_id(info["payee_name"], city, salt)
        stable_seed = int(hashlib.sha256(norm.encode()).hexdigest()[:8], 16)
        lat_approx, lng_approx = jitter_location(lat, lng, seed=stable_seed)

        pub = PhysicianPublic(
            physician_id=raw.id,
            pseudo_id=pseudo,
            specialty=None,
            specialty_group="Unknown",
            lat_approx=lat_approx,
            lng_approx=lng_approx,
            city=city.title(),
            health_authority=info["health_authority"],
        )
        db.add(pub)

        # Billings
        for bill in billings_by_name[norm]:
            b = Billing(
                physician_id=raw.id,
                year=bill["year"],
                total_billings=bill["amount"],
            )
            db.add(b)

        if (i + 1) % 2000 == 0:
            db.commit()
            print(f"  {i + 1:,} / {len(physician_map):,} physicians...")

    db.commit()
    print(f"  Wrote {len(physician_map):,} physicians + {len(all_rows):,} billing records")

    # ── Stage 4: Compute aggregations ────────────────────────────────
    print("Computing aggregations...")
    _compute_aggregations(db, physician_ids, billings_by_name, physician_map)
    db.commit()

    db.close()
    print("\nPipeline complete.")


def _compute_aggregations(
    db: Session,
    physician_ids: dict[str, int],
    billings_by_name: dict[str, list[dict]],
    physician_map: dict[str, dict],
):
    """Compute city-level aggregations with k-anonymity."""
    # Group billings by (year, city)
    year_city_amounts: dict[tuple[str, str], list[float]] = defaultdict(list)
    year_city_physicians: dict[tuple[str, str], set[str]] = defaultdict(set)

    for norm, bills in billings_by_name.items():
        city = physician_map[norm]["city"].title()
        for bill in bills:
            key = (bill["year"], city)
            year_city_amounts[key].append(bill["amount"])
            year_city_physicians[key].add(norm)

    k_min = 5
    count = 0
    for (year, city), amounts in year_city_amounts.items():
        n_phys = len(year_city_physicians[(year, city)])
        suppressed = n_phys < k_min

        agg = Aggregation(
            fiscal_year=year,
            geo_level="city",
            geo_id=city.lower().replace(" ", "_"),
            geo_name=city,
            specialty_group="All",
            n_physicians=n_phys,
            total_payments=round(sum(amounts), 2) if not suppressed else 0,
            median_payments=round(statistics.median(amounts), 2) if not suppressed else None,
            suppressed=suppressed,
            suppression_reason="k_min" if suppressed else None,
        )
        db.add(agg)
        count += 1

    print(f"  {count} aggregation cells")


if __name__ == "__main__":
    run()
