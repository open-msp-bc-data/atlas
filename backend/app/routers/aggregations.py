"""Aggregation endpoints – public, privacy-safe summaries."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Aggregation
from ..schemas import AggregationOut

router = APIRouter(tags=["aggregations"])


@router.get("/aggregations", response_model=list[AggregationOut])
def list_aggregations(
    geo_level: str | None = Query(None, description="facility, city, or ha"),
    fiscal_year: str | None = Query(None),
    specialty_group: str | None = Query(None),
    include_suppressed: bool = Query(False),
    limit: int = Query(200, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Return pre-computed aggregations.  Suppressed cells are hidden by default."""
    q = db.query(Aggregation)
    if geo_level:
        q = q.filter(Aggregation.geo_level == geo_level)
    if fiscal_year:
        q = q.filter(Aggregation.fiscal_year == fiscal_year)
    if specialty_group:
        q = q.filter(Aggregation.specialty_group == specialty_group)
    if not include_suppressed:
        q = q.filter(Aggregation.suppressed == False)  # noqa: E712

    return q.offset(offset).limit(limit).all()
