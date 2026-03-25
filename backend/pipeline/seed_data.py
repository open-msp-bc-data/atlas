"""Seed data generator – creates realistic demo data for development and testing."""

from __future__ import annotations

import random
import sys
from pathlib import Path

# Ensure the backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import init_db, get_engine
from app.models import PhysicianRaw, Billing, PhysicianPublic, Aggregation
from app.privacy import deterministic_pseudo_id, jitter_location, generalize_specialty
from pipeline.geocode import BC_CITY_CENTROIDS, CITY_TO_HEALTH_AUTHORITY

from sqlalchemy.orm import Session

# ── Sample data pools ─────────────────────────────────────────────────
FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael",
    "Linda", "David", "Elizabeth", "William", "Barbara", "Richard", "Susan",
    "Joseph", "Jessica", "Thomas", "Sarah", "Christopher", "Karen",
    "Daniel", "Lisa", "Matthew", "Nancy", "Anthony", "Betty", "Mark",
    "Margaret", "Donald", "Sandra", "Steven", "Ashley", "Paul", "Dorothy",
    "Andrew", "Kimberly", "Joshua", "Emily", "Kenneth", "Donna",
    "Wei", "Xin", "Priya", "Raj", "Harpreet", "Gurpreet", "Ahmed",
    "Fatima", "Yuki", "Hiroshi", "Elena", "Dmitri", "Olga", "Ivan",
    "Ananya", "Vikram", "Meera", "Arjun", "Nadia", "Tariq",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Chen", "Wang", "Kim", "Singh", "Patel", "Nguyen", "Li",
    "Zhang", "Liu", "Huang", "Wu", "Yang", "Kumar", "Sharma", "Gupta",
    "Kaur", "Gill", "Dhillon", "Sidhu", "Sandhu", "Grewal", "Bains",
    "Takahashi", "Yamamoto", "Suzuki", "Petrov", "Ivanov", "Moreau",
]

SPECIALTIES = [
    "Family Medicine", "Internal Medicine", "General Surgery", "Pediatrics",
    "Psychiatry", "Obstetrics and Gynecology", "Anesthesiology",
    "Diagnostic Radiology", "Emergency Medicine", "Orthopedic Surgery",
    "Cardiology", "Dermatology", "Neurology", "Ophthalmology",
    "Pathology", "Urology", "Gastroenterology", "Nephrology",
    "Physical Medicine", "Plastic Surgery", "Neurosurgery",
    "Radiation Oncology", "Rheumatology", "Endocrinology",
]

YEARS = ["2021-2022", "2022-2023", "2023-2024"]


def generate_seed_data(n_physicians: int = 150, seed: int = 42):
    """Generate and insert demo physician + billing data into the database."""
    rng = random.Random(seed)
    init_db()

    engine = get_engine()
    from sqlalchemy.orm import sessionmaker
    SessionLocal = sessionmaker(bind=engine)
    db: Session = SessionLocal()

    # Clear existing data
    db.query(Aggregation).delete()
    db.query(PhysicianPublic).delete()
    db.query(Billing).delete()
    db.query(PhysicianRaw).delete()
    db.commit()

    cities = list(BC_CITY_CENTROIDS.keys())
    physicians = []

    for i in range(n_physicians):
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        full_name = f"Dr. {first} {last}"
        specialty = rng.choice(SPECIALTIES)
        city = rng.choice(cities)
        lat, lng = BC_CITY_CENTROIDS[city]
        ha = CITY_TO_HEALTH_AUTHORITY.get(city, "Unknown")

        phys = PhysicianRaw(
            full_name=full_name,
            specialty=specialty,
            address=f"{rng.randint(100, 9999)} {rng.choice(['Main', 'Oak', 'Cedar', 'Maple', 'Broadway', 'Granville', 'Hastings', 'Kingsway'])} St",
            city=city.title(),
            health_authority=ha,
            lat=lat,
            lng=lng,
            license_status="Active" if rng.random() > 0.05 else "Inactive",
            cpsbc_id=f"CPSBC-{10000 + i}",
        )
        db.add(phys)
        db.flush()  # get ID

        # Create billings (base amount with YoY growth + noise)
        base = rng.uniform(100_000, 800_000)
        for year in YEARS:
            growth = rng.uniform(-0.05, 0.15)
            base = base * (1 + growth)
            billing = Billing(
                physician_id=phys.id,
                year=year,
                total_billings=round(base, 2),
            )
            db.add(billing)

        # Create public record
        pseudo = deterministic_pseudo_id(full_name)
        lat_approx, lng_approx = jitter_location(lat, lng, seed=hash(full_name) % 2**31)
        pub = PhysicianPublic(
            physician_id=phys.id,
            pseudo_id=pseudo,
            specialty=specialty,
            specialty_group=generalize_specialty(specialty),
            lat_approx=lat_approx,
            lng_approx=lng_approx,
            city=city.title(),
            health_authority=ha,
        )
        db.add(pub)
        physicians.append(phys)

    db.commit()

    # Create aggregations
    _generate_aggregations(db, physicians)

    db.commit()
    db.close()
    print(f"✓ Seeded {n_physicians} physicians with billings and aggregations.")


def _generate_aggregations(db: Session, physicians: list):
    """Compute and insert city-level and HA-level aggregations."""
    from collections import defaultdict
    import statistics

    for year in YEARS:
        # City-level
        city_groups: dict[str, list[float]] = defaultdict(list)
        ha_groups: dict[str, list[float]] = defaultdict(list)

        for phys in physicians:
            billing = (
                db.query(Billing)
                .filter(Billing.physician_id == phys.id, Billing.year == year)
                .first()
            )
            if billing:
                city = phys.city or "Unknown"
                ha = phys.health_authority or "Unknown"
                city_groups[city].append(billing.total_billings)
                ha_groups[ha].append(billing.total_billings)

        for city, amounts in city_groups.items():
            suppressed = len(amounts) < 5
            agg = Aggregation(
                fiscal_year=year,
                geo_level="city",
                geo_id=city.lower().replace(" ", "_"),
                geo_name=city,
                specialty_group="All",
                n_physicians=len(amounts),
                total_payments=round(sum(amounts), 2) if not suppressed else 0,
                median_payments=round(statistics.median(amounts), 2) if not suppressed else None,
                suppressed=suppressed,
                suppression_reason="k_min" if suppressed else None,
            )
            db.add(agg)

        for ha, amounts in ha_groups.items():
            suppressed = len(amounts) < 5
            agg = Aggregation(
                fiscal_year=year,
                geo_level="ha",
                geo_id=ha.lower().replace(" ", "_"),
                geo_name=ha,
                specialty_group="All",
                n_physicians=len(amounts),
                total_payments=round(sum(amounts), 2) if not suppressed else 0,
                median_payments=round(statistics.median(amounts), 2) if not suppressed else None,
                suppressed=suppressed,
                suppression_reason="k_min" if suppressed else None,
            )
            db.add(agg)


if __name__ == "__main__":
    generate_seed_data()
