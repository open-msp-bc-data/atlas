"""Public physician endpoints (anonymised)."""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..auth import validate_admin_token
from ..config import get_privacy_config
from ..database import get_db
from ..models import PhysicianPublic, Billing
from ..schemas import PhysicianPublicOut, HeatmapCell, PhysicianTrendOut, TrendPoint
from ..privacy import billing_range

router = APIRouter(tags=["physicians"])

# Grid cell size for heatmap privacy (in degrees, ~3.7–5.6km across BC latitudes)
_HEATMAP_GRID_SIZE = 0.05

# Simple in-memory rate limiter for /trends endpoint
_RATE_LIMIT_WINDOW = 60  # seconds
_RATE_LIMIT_MAX = 30  # requests per window per IP
_rate_limit_store: dict[str, list[float]] = defaultdict(list)


@router.get("/physicians", response_model=list[PhysicianPublicOut])
def list_physicians(
    specialty: str | None = Query(None),
    city: str | None = Query(None),
    health_authority: str | None = Query(None),
    year: str | None = Query(None, description="Fiscal year for billing range/YoY (e.g. 2023-2024)"),
    k_anonymity: str = Query("on", description="Set to 'off' with admin token to bypass query-level k-anonymity"),
    limit: int = Query(200, le=1000),
    offset: int = Query(0, ge=0),
    x_admin_token: str | None = Header(None),
    db: Session = Depends(get_db),
):
    """Return anonymised physician records for public map display.

    Query-level k-anonymity: if the filter combination returns fewer than
    k_min distinct physicians, a suppression notice is returned instead of
    individual records. Admin users can bypass this with a valid token.
    """
    q = db.query(PhysicianPublic)
    if specialty:
        q = q.filter(PhysicianPublic.specialty_group == specialty)
    if city:
        q = q.filter(PhysicianPublic.city == city)
    if health_authority:
        q = q.filter(PhysicianPublic.health_authority == health_authority)

    # Query-level k-anonymity check
    k_min = get_privacy_config().get("k_min_unique_phys", 5)
    bypass = k_anonymity == "off" and validate_admin_token(x_admin_token)

    if not bypass:
        total_matching = q.count()
        if total_matching < k_min and total_matching > 0:
            return JSONResponse(content={
                "suppressed": True,
                "reason": "query_k_anonymity",
                "message": f"Filter combination returns fewer than {k_min} individuals. "
                           "Results suppressed to prevent re-identification.",
            })

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


@router.get("/heatmap", response_model=list[HeatmapCell])
def heatmap(
    year: str | None = Query(None),
    k_anonymity: str = Query("on"),
    x_admin_token: str | None = Header(None),
    db: Session = Depends(get_db),
):
    """Return spatially-grouped billing intensity for heatmap rendering.

    Points are grouped into ~5km grid cells to prevent individual physician
    locations from being inferred. Grid cells with fewer than k_min physicians
    are suppressed.
    """
    k_min = get_privacy_config().get("k_min_unique_phys", 5)
    bypass = k_anonymity == "off" and validate_admin_token(x_admin_token)

    # Round coordinates to grid cells for privacy
    grid = _HEATMAP_GRID_SIZE
    lat_cell = func.round(PhysicianPublic.lat_approx / grid) * grid
    lng_cell = func.round(PhysicianPublic.lng_approx / grid) * grid

    q = db.query(
        lat_cell.label("lat"),
        lng_cell.label("lng"),
        func.sum(Billing.total_billings).label("intensity"),
        func.count(func.distinct(PhysicianPublic.id)).label("n_physicians"),
    ).join(Billing, Billing.physician_id == PhysicianPublic.physician_id)

    if year:
        q = q.filter(Billing.year == year)

    q = q.filter(
        PhysicianPublic.lat_approx.isnot(None),
        PhysicianPublic.lng_approx.isnot(None),
    ).group_by(lat_cell, lng_cell)

    cells = []
    for row in q.all():
        if not bypass and row.n_physicians < k_min:
            continue
        cells.append(HeatmapCell(
            lat=row.lat,
            lng=row.lng,
            intensity=row.intensity,
            n_physicians=row.n_physicians,
        ))
    return cells


def _check_rate_limit(client_ip: str) -> None:
    """Enforce per-IP rate limiting. Raises 429 if exceeded."""
    now = time.time()
    timestamps = _rate_limit_store[client_ip]
    # Prune old entries
    cutoff = now - _RATE_LIMIT_WINDOW
    _rate_limit_store[client_ip] = [t for t in timestamps if t > cutoff]
    if len(_rate_limit_store[client_ip]) >= _RATE_LIMIT_MAX:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    _rate_limit_store[client_ip].append(now)


@router.get("/trends/{pseudo_id}", response_model=PhysicianTrendOut)
def physician_trend(pseudo_id: str, db: Session = Depends(get_db)):
    """Return year-over-year billing trend for a single anonymised physician."""
    # Basic rate limiting to prevent pseudo_id enumeration
    _check_rate_limit(pseudo_id)

    pub = db.query(PhysicianPublic).filter(PhysicianPublic.pseudo_id == pseudo_id).first()
    if pub is None:
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
