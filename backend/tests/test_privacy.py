"""Tests for the privacy module."""

from __future__ import annotations

import pytest

from app.privacy import (
    deterministic_pseudo_id,
    jitter_location,
    generalize_specialty,
    apply_k_anonymity,
    apply_dominance_suppression,
    billing_range,
)


class TestDeterministicPseudoId:
    def test_format(self):
        pid = deterministic_pseudo_id("Dr. John Smith", salt="test")
        assert pid.startswith("PHY-")
        assert len(pid) == 36  # PHY- + 32 hex chars

    def test_deterministic(self):
        a = deterministic_pseudo_id("Dr. John Smith", salt="test")
        b = deterministic_pseudo_id("Dr. John Smith", salt="test")
        assert a == b

    def test_different_names(self):
        a = deterministic_pseudo_id("Dr. John Smith", salt="test")
        b = deterministic_pseudo_id("Dr. Jane Doe", salt="test")
        assert a != b

    def test_different_salts(self):
        a = deterministic_pseudo_id("Dr. John Smith", salt="salt1")
        b = deterministic_pseudo_id("Dr. John Smith", salt="salt2")
        assert a != b

    def test_different_cities(self):
        a = deterministic_pseudo_id("Dr. John Smith", city="Vancouver", salt="test")
        b = deterministic_pseudo_id("Dr. John Smith", city="Victoria", salt="test")
        assert a != b

    def test_normalization(self):
        """Case and whitespace should not affect the output."""
        a = deterministic_pseudo_id("Dr. JOHN SMITH", city="VANCOUVER", salt="test")
        b = deterministic_pseudo_id("dr. john smith", city="vancouver", salt="test")
        assert a == b

    def test_normalization_strips_whitespace(self):
        a = deterministic_pseudo_id("  Dr. John Smith  ", city=" Vancouver ", salt="test")
        b = deterministic_pseudo_id("Dr. John Smith", city="Vancouver", salt="test")
        assert a == b


class TestJitterLocation:
    def test_returns_tuple(self):
        lat, lng = jitter_location(49.2827, -123.1207, max_km=1.0, seed=42)
        assert isinstance(lat, float)
        assert isinstance(lng, float)

    def test_within_range(self):
        orig_lat, orig_lng = 49.2827, -123.1207
        for seed in range(100):
            lat, lng = jitter_location(orig_lat, orig_lng, max_km=2.0, seed=seed)
            # 2 km ≈ 0.018 degrees latitude
            assert abs(lat - orig_lat) < 0.025
            assert abs(lng - orig_lng) < 0.035

    def test_deterministic_with_seed(self):
        a = jitter_location(49.0, -123.0, max_km=1.0, seed=42)
        b = jitter_location(49.0, -123.0, max_km=1.0, seed=42)
        assert a == b

    def test_different_seeds_differ(self):
        a = jitter_location(49.0, -123.0, max_km=1.0, seed=1)
        b = jitter_location(49.0, -123.0, max_km=1.0, seed=2)
        assert a != b


class TestGeneralizeSpecialty:
    def test_known_specialty(self):
        assert generalize_specialty("Family Medicine") == "General Practice"
        assert generalize_specialty("Cardiology") == "Internal Medicine"
        assert generalize_specialty("General Surgery") == "Surgery"

    def test_case_insensitive(self):
        assert generalize_specialty("FAMILY MEDICINE") == "General Practice"
        assert generalize_specialty("cardiology") == "Internal Medicine"

    def test_unknown(self):
        assert generalize_specialty("Made Up Specialty") == "Other Specialty"

    def test_none(self):
        assert generalize_specialty(None) == "Unknown"

    def test_empty(self):
        assert generalize_specialty("") == "Unknown"


class TestKAnonymity:
    def test_suppresses_small_groups(self):
        records = [
            {"geo_id": "a", "n_physicians": 3, "total_payments": 1000, "median_payments": 500, "pct_change_yoy": 0.1},
            {"geo_id": "b", "n_physicians": 10, "total_payments": 5000, "median_payments": 500, "pct_change_yoy": 0.2},
        ]
        result = apply_k_anonymity(records, k_min=5)
        assert result[0]["suppressed"] is True
        assert result[0]["suppression_reason"] == "k_min"
        assert result[0]["total_payments"] is None

    def test_keeps_large_groups(self):
        records = [
            {"geo_id": "b", "n_physicians": 10, "total_payments": 5000, "median_payments": 500, "pct_change_yoy": 0.2},
        ]
        result = apply_k_anonymity(records, k_min=5)
        assert result[0].get("suppressed", False) is False
        assert result[0]["total_payments"] == 5000


class TestDominanceSuppression:
    def test_suppresses_dominant(self):
        records = [{"geo_id": "a", "max_share": 0.8, "total_payments": 1000, "median_payments": 500}]
        result = apply_dominance_suppression(records, dominance_threshold=0.6)
        assert result[0]["suppressed"] is True
        assert result[0]["suppression_reason"] == "dominance"

    def test_keeps_non_dominant(self):
        records = [{"geo_id": "a", "max_share": 0.3, "total_payments": 1000, "median_payments": 500}]
        result = apply_dominance_suppression(records, dominance_threshold=0.6)
        assert result[0].get("suppressed", False) is False

    def test_does_not_overwrite_k_min_suppression(self):
        """Dominance suppression should not overwrite prior k_min suppression."""
        records = [{
            "geo_id": "a",
            "max_share": 0.8,
            "total_payments": None,
            "median_payments": None,
            "suppressed": True,
            "suppression_reason": "k_min",
        }]
        result = apply_dominance_suppression(records, dominance_threshold=0.6)
        assert result[0]["suppressed"] is True
        assert result[0]["suppression_reason"] == "k_min"  # preserved, not overwritten


class TestBillingRange:
    def test_standard_range(self):
        assert billing_range(237_000) == "230k\u2013240k"

    def test_low_range(self):
        assert billing_range(45_000) == "40k\u201350k"

    def test_exact_boundary(self):
        assert billing_range(200_000) == "200k\u2013210k"

    def test_custom_step(self):
        assert billing_range(237_000, step=100_000) == "200k\u2013300k"
