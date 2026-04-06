"""Aggregation endpoints – public, privacy-safe summaries."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Aggregation
from ..schemas import AggregationOut

router = APIRouter(tags=["aggregations"])

_VALID_GEO_LEVELS = {"facility", "city", "ha"}


@router.get("/aggregations", response_model=list[AggregationOut])
def list_aggregations(
    geo_level: str | None = Query(None, description="facility, city, or ha"),
    fiscal_year: str | None = Query(None, pattern=r"^\d{4}-\d{4}$"),
    specialty_group: str | None = Query(None),
    include_suppressed: bool = Query(False),
    limit: int = Query(200, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Return pre-computed aggregations.  Suppressed cells are hidden by default."""
    if geo_level and geo_level not in _VALID_GEO_LEVELS:
        raise HTTPException(status_code=422, detail=f"geo_level must be one of: {', '.join(sorted(_VALID_GEO_LEVELS))}")
    q = db.query(Aggregation)
    if geo_level:
        q = q.filter(Aggregation.geo_level == geo_level)
    if fiscal_year:
        q = q.filter(Aggregation.fiscal_year == fiscal_year)
    if specialty_group:
        q = q.filter(Aggregation.specialty_group == specialty_group)
    if not include_suppressed:
        q = q.filter(Aggregation.suppressed.is_(False))

    return q.offset(offset).limit(limit).all()
