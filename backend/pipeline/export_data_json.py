"""Export the database to frontend/public/data.json for static site deployment.

Usage:
    cd backend
    PRIVACY_SALT="your-secret" python -m pipeline.export_data_json
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import init_db, get_engine
from app.models import PhysicianPublic, Billing, Aggregation
from app.privacy import billing_range
from sqlalchemy.orm import sessionmaker


OUTPUT = Path(__file__).resolve().parent.parent.parent / "frontend" / "public" / "data.json"


def export():
    init_db()
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    db = Session()

    # ── Physicians ───────────────────────────────────────────────────
    physicians = []
    pubs = db.query(PhysicianPublic).all()

    # Pre-fetch all billings
    all_billings = db.query(Billing).order_by(Billing.year).all()
    billings_by_pid = defaultdict(list)
    for b in all_billings:
        billings_by_pid[b.physician_id].append(b)

    all_years = set()
    for pub in pubs:
        bills = billings_by_pid.get(pub.physician_id, [])
        billing_years = []
        for b in bills:
            all_years.add(b.year)
            billing_years.append({
                "year": b.year,
                "billing_range": billing_range(b.total_billings),
            })

        # Latest and previous for YoY
        latest = bills[-1] if bills else None
        prev = bills[-2] if len(bills) >= 2 else None
        yoy = None
        if latest and prev and prev.total_billings > 0:
            yoy = round((latest.total_billings - prev.total_billings) / prev.total_billings, 4)

        physicians.append({
            "pseudo_id": pub.pseudo_id,
            "specialty_group": pub.specialty_group or "Unknown",
            "lat_approx": pub.lat_approx,
            "lng_approx": pub.lng_approx,
            "city": pub.city,
            "health_authority": pub.health_authority,
            "latest_billing_range": billing_range(latest.total_billings) if latest else None,
            "yoy_change": yoy,
            "billing_years": billing_years,
        })

    # ── Aggregations ─────────────────────────────────────────────────
    aggs = db.query(Aggregation).filter(Aggregation.suppressed.is_(False)).all()
    aggregations = defaultdict(list)
    for a in aggs:
        all_years.add(a.fiscal_year)
        aggregations[a.fiscal_year].append({
            "geo_name": a.geo_name,
            "geo_level": a.geo_level,
            "n_physicians": a.n_physicians,
            "total_payments": a.total_payments,
            "median_payments": a.median_payments,
            "pct_change_yoy": a.pct_change_yoy,
            "suppressed": a.suppressed,
        })

    years = sorted(all_years, key=lambda y: int(y.split("-")[0]))

    output = {
        "physicians": physicians,
        "aggregations": dict(aggregations),
        "years": years,
        "generated": date.today().isoformat(),
        "total_physicians": len(physicians),
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump(output, f)

    print(f"Exported {len(physicians):,} physicians, {len(years)} years")
    print(f"  Aggregation years: {years}")
    print(f"  Output: {OUTPUT} ({OUTPUT.stat().st_size / 1024 / 1024:.1f} MB)")

    db.close()


if __name__ == "__main__":
    export()
