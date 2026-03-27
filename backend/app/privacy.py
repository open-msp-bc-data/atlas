"""Privacy module – location jitter, deterministic hashing, k-anonymity enforcement."""

from __future__ import annotations

import hashlib
import math
import random
from typing import Any

from .config import get_privacy_config


def deterministic_pseudo_id(full_name: str, salt: str | None = None) -> str:
    """Generate a deterministic anonymised identifier from a physician name.

    Returns a string like ``PHY-A1B2C3D4``.
    """
    if salt is None:
        salt = get_privacy_config().get("salt", "")
    digest = hashlib.sha256(f"{salt}:{full_name}".encode()).hexdigest()[:8].upper()
    return f"PHY-{digest}"


def jitter_location(
    lat: float,
    lng: float,
    max_km: float | None = None,
    seed: int | None = None,
) -> tuple[float, float]:
    """Add uniform random jitter to a coordinate pair.

    *max_km* defaults to the ``location_jitter_km`` config value (typically 1–2 km).
    Returns ``(lat_approx, lng_approx)`` rounded to 4 decimal places.
    """
    if max_km is None:
        max_km = get_privacy_config().get("location_jitter_km", 1.5)

    rng = random.Random(seed)  # deterministic if seed is given
    # Convert km offset to degrees (approximate)
    km_per_deg_lat = 111.32
    km_per_deg_lng = 111.32 * math.cos(math.radians(lat))

    d_lat = rng.uniform(-max_km, max_km) / km_per_deg_lat
    d_lng = rng.uniform(-max_km, max_km) / max(km_per_deg_lng, 0.001)

    return round(lat + d_lat, 4), round(lng + d_lng, 4)


def generalize_specialty(specialty: str | None) -> str:
    """Map fine-grained specialty to a broader group for public display."""
    if not specialty:
        return "Unknown"
    specialty_lower = specialty.lower()
    mapping = {
        "family medicine": "General Practice",
        "general practice": "General Practice",
        "family practice": "General Practice",
        "internal medicine": "Internal Medicine",
        "cardiology": "Internal Medicine",
        "gastroenterology": "Internal Medicine",
        "nephrology": "Internal Medicine",
        "rheumatology": "Internal Medicine",
        "endocrinology": "Internal Medicine",
        "general surgery": "Surgery",
        "orthopedic surgery": "Surgery",
        "orthopaedic surgery": "Surgery",
        "cardiac surgery": "Surgery",
        "neurosurgery": "Surgery",
        "plastic surgery": "Surgery",
        "vascular surgery": "Surgery",
        "urology": "Surgery",
        "obstetrics": "Obstetrics & Gynecology",
        "gynecology": "Obstetrics & Gynecology",
        "obstetrics and gynecology": "Obstetrics & Gynecology",
        "pediatrics": "Pediatrics",
        "psychiatry": "Psychiatry",
        "anesthesiology": "Anesthesiology",
        "diagnostic radiology": "Radiology",
        "radiology": "Radiology",
        "radiation oncology": "Radiology",
        "emergency medicine": "Emergency Medicine",
        "pathology": "Pathology",
        "dermatology": "Dermatology",
        "ophthalmology": "Ophthalmology",
        "neurology": "Neurology",
        "physical medicine": "Physical Medicine",
        "nuclear medicine": "Other Specialty",
        "medical microbiology": "Other Specialty",
        "public health": "Other Specialty",
    }
    return mapping.get(specialty_lower, "Other Specialty")


def apply_k_anonymity(
    records: list[dict[str, Any]],
    k_min: int | None = None,
) -> list[dict[str, Any]]:
    """Suppress records where the number of unique physicians is below *k_min*.

    Each record dict must contain an ``"n_physicians"`` key indicating the
    count of unique physicians contributing to that record.

    Returns the list with ``suppressed=True`` and ``suppression_reason`` set
    for records that fail the threshold.
    """
    if k_min is None:
        k_min = get_privacy_config().get("k_min_unique_phys", 5)

    result = []
    for rec in records:
        rec = dict(rec)  # shallow copy
        if rec.get("n_physicians", 0) < k_min:
            rec["suppressed"] = True
            rec["suppression_reason"] = "k_min"
            rec["total_payments"] = None
            rec["median_payments"] = None
            rec["pct_change_yoy"] = None
        result.append(rec)
    return result


def apply_dominance_suppression(
    records: list[dict[str, Any]],
    dominance_threshold: float | None = None,
) -> list[dict[str, Any]]:
    """Suppress cells where one contributor dominates the total."""
    if dominance_threshold is None:
        dominance_threshold = get_privacy_config().get("dominance_threshold", 0.60)

    result = []
    for rec in records:
        rec = dict(rec)
        if rec.get("max_share", 0) >= dominance_threshold:
            rec["suppressed"] = True
            rec["suppression_reason"] = "dominance"
            rec["total_payments"] = None
            rec["median_payments"] = None
        result.append(rec)
    return result


def billing_range(amount: float, step: int = 50_000) -> str:
    """Convert an exact billing amount to a range string for public display.

    Example: 237_000 → ``"200k–250k"``
    """
    lower = int(amount // step) * step
    upper = lower + step
    return f"{lower // 1000}k\u2013{upper // 1000}k"
