"""Pydantic response schemas for the public API."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


# ── Public physician (anonymised) ──────────────────────────────────────
class PhysicianPublicOut(BaseModel):
    pseudo_id: str
    specialty: Optional[str] = None
    specialty_group: Optional[str] = None
    lat_approx: Optional[float] = None
    lng_approx: Optional[float] = None
    city: Optional[str] = None
    health_authority: Optional[str] = None
    latest_billing_range: Optional[str] = None
    yoy_change: Optional[float] = None

    model_config = {"from_attributes": True}


# ── Aggregation ────────────────────────────────────────────────────────
class AggregationOut(BaseModel):
    fiscal_year: str
    geo_level: str
    geo_id: str
    geo_name: str
    specialty_group: Optional[str] = None
    n_physicians: int
    total_payments: Optional[float] = None
    median_payments: Optional[float] = None
    pct_change_yoy: Optional[float] = None
    suppressed: bool = False
    suppression_reason: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Trend (time-series per pseudo_id) ─────────────────────────────────
class TrendPoint(BaseModel):
    year: str
    billing_range: Optional[str] = None


class PhysicianTrendOut(BaseModel):
    pseudo_id: str
    specialty_group: Optional[str] = None
    data: list[TrendPoint] = []


# ── Heatmap point ─────────────────────────────────────────────────────
class HeatmapPoint(BaseModel):
    lat: float
    lng: float
    intensity: float


# ── Admin raw physician ───────────────────────────────────────────────
class PhysicianRawOut(BaseModel):
    id: int
    full_name: str
    specialty: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    health_authority: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    license_status: Optional[str] = None

    model_config = {"from_attributes": True}
