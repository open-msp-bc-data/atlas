"""Public physician endpoints (anonymised)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

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

    results = []
    for rec in records:
        # Fetch latest billing for this physician
        latest = (
            db.query(Billing)
            .filter(Billing.physician_id == rec.physician_id)
            .order_by(desc(Billing.year))
            .first()
        )
        # Fetch second-latest for YoY
        prev = (
            db.query(Billing)
            .filter(Billing.physician_id == rec.physician_id)
            .order_by(desc(Billing.year))
            .offset(1)
            .first()
        )
        latest_range = billing_range(latest.total_billings) if latest else None
        yoy = None
        if latest and prev and prev.total_billings > 0:
            yoy = round((latest.total_billings - prev.total_billings) / prev.total_billings, 4)

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

    q = q.group_by(PhysicianPublic.id).having(
        PhysicianPublic.lat_approx.isnot(None),
        PhysicianPublic.lng_approx.isnot(None),
    )

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
