"""Public physician endpoints (anonymised)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from ..models import PhysicianPublic, Billing
from ..schemas import PhysicianPublicOut, HeatmapPoint, PhysicianTrendOut, TrendPoint
from ..privacy import billing_range

router = APIRouter(tags=["physicians"])


@router.get("/physicians", response_model=list[PhysicianPublicOut])
def list_physicians(
    specialty: str | None = Query(None),
    city: str | None = Query(None),
    health_authority: str | None = Query(None),
    year: str | None = Query(None, description="Fiscal year for billing range/YoY (e.g. 2023-2024)"),
    limit: int = Query(200, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Return anonymised physician records for public map display."""
    q = db.query(PhysicianPublic)
    if specialty:
        q = q.filter(PhysicianPublic.specialty_group == specialty)
    if city:
        q = q.filter(PhysicianPublic.city == city)
    if health_authority:
        q = q.filter(PhysicianPublic.health_authority == health_authority)

    records = q.offset(offset).limit(limit).all()

    if not records:
        return []

    # Batch-fetch latest and previous billings for all physicians to avoid N+1 queries
    physician_ids = [rec.physician_id for rec in records]

    billing_base = db.query(
        Billing.physician_id.label("physician_id"),
        Billing.total_billings.label("total_billings"),
        Billing.year.label("year"),
        func.row_number()
        .over(
            partition_by=Billing.physician_id,
            order_by=Billing.year.desc(),
        )
        .label("rn"),
    ).filter(Billing.physician_id.in_(physician_ids))

    # When a specific year is requested, only consider that year and earlier
    if year:
        billing_base = billing_base.filter(Billing.year <= year)

    billing_subq = billing_base.subquery()

    billing_rows = (
        db.query(
            billing_subq.c.physician_id,
            billing_subq.c.total_billings,
            billing_subq.c.rn,
        )
        .filter(billing_subq.c.rn.in_([1, 2]))
        .all()
    )

    # Map: physician_id -> {1: latest_total, 2: previous_total}
    billing_map: dict[int, dict[int, float]] = {}
    for row in billing_rows:
        pid = row.physician_id
        rn = row.rn
        billing_map.setdefault(pid, {})[rn] = row.total_billings

    results = []
    for rec in records:
        pid = rec.physician_id
        latest_total = billing_map.get(pid, {}).get(1)
        prev_total = billing_map.get(pid, {}).get(2)

        latest_range = billing_range(latest_total) if latest_total is not None else None
        yoy = None
        if (
            latest_total is not None
            and prev_total is not None
            and prev_total > 0
        ):
            yoy = round((latest_total - prev_total) / prev_total, 4)

        results.append(
            PhysicianPublicOut(
                pseudo_id=rec.pseudo_id,
                specialty=rec.specialty,
                specialty_group=rec.specialty_group,
                lat_approx=rec.lat_approx,
                lng_approx=rec.lng_approx,
                city=rec.city,
                health_authority=rec.health_authority,
                latest_billing_range=latest_range,
                yoy_change=yoy,
            )
        )
    return results


@router.get("/heatmap", response_model=list[HeatmapPoint])
def heatmap(
    year: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """Return approximate physician locations weighted by billing for heatmap rendering."""
    q = db.query(
        PhysicianPublic.lat_approx,
        PhysicianPublic.lng_approx,
        func.sum(Billing.total_billings).label("intensity"),
    ).join(Billing, Billing.physician_id == PhysicianPublic.physician_id)

    if year:
        q = q.filter(Billing.year == year)

    q = q.filter(
        PhysicianPublic.lat_approx.isnot(None),
        PhysicianPublic.lng_approx.isnot(None),
    ).group_by(PhysicianPublic.id)

    return [
        HeatmapPoint(lat=row.lat_approx, lng=row.lng_approx, intensity=row.intensity)
        for row in q.all()
    ]


@router.get("/trends/{pseudo_id}", response_model=PhysicianTrendOut)
def physician_trend(pseudo_id: str, db: Session = Depends(get_db)):
    """Return year-over-year billing trend for a single anonymised physician."""
    pub = db.query(PhysicianPublic).filter(PhysicianPublic.pseudo_id == pseudo_id).first()
    if pub is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Physician not found")

    bills = (
        db.query(Billing)
        .filter(Billing.physician_id == pub.physician_id)
        .order_by(Billing.year)
        .all()
    )
    return PhysicianTrendOut(
        pseudo_id=pub.pseudo_id,
        specialty_group=pub.specialty_group,
        data=[TrendPoint(year=b.year, billing_range=billing_range(b.total_billings)) for b in bills],
    )
