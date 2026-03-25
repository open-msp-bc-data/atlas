"""Tests for pipeline modules."""

from __future__ import annotations

import pytest

from pipeline.entity_resolution import normalize_name, build_entity_key, match_payee_to_registrants, resolve_entities
from pipeline.geocode import geocode_address, _city_centroid_fallback, _lookup_health_authority, BC_CITY_CENTROIDS
from pipeline.ingest_bluebook import extract_fiscal_year, _parse_row


class TestNormalizeName:
    def test_removes_title(self):
        assert "john smith" in normalize_name("Dr. John Smith")

    def test_removes_credentials(self):
        result = normalize_name("Dr. John Smith MD FRCPC")
        assert "frcpc" not in result
        assert "md" not in result

    def test_collapses_whitespace(self):
        result = normalize_name("  Dr.  John   Smith  ")
        assert "  " not in result


class TestBuildEntityKey:
    def test_deterministic(self):
        a = build_entity_key("Dr. John Smith", "Vancouver", salt="s")
        b = build_entity_key("Dr. John Smith", "Vancouver", salt="s")
        assert a == b

    def test_different_city(self):
        a = build_entity_key("Dr. John Smith", "Vancouver", salt="s")
        b = build_entity_key("Dr. John Smith", "Victoria", salt="s")
        assert a != b

    def test_sha256_length(self):
        key = build_entity_key("Dr. Test", "City", salt="")
        assert len(key) == 64  # SHA-256 hex digest


class TestFuzzyMatching:
    @pytest.fixture
    def registrants(self):
        return [
            {"full_name": "John Smith", "city": "Vancouver", "cpsbc_id": "C1", "specialty": "Family Medicine"},
            {"full_name": "Jane Doe", "city": "Victoria", "cpsbc_id": "C2", "specialty": "Cardiology"},
            {"full_name": "Robert Johnson", "city": "Kelowna", "cpsbc_id": "C3", "specialty": "Pediatrics"},
        ]

    def test_exact_match(self, registrants):
        result = match_payee_to_registrants("John Smith", registrants)
        assert result is not None
        assert result["cpsbc_id"] == "C1"

    def test_fuzzy_match(self, registrants):
        result = match_payee_to_registrants("J. Smith", registrants, threshold=70)
        # Should match John Smith with a reasonable score
        assert result is not None

    def test_no_match(self, registrants):
        result = match_payee_to_registrants("Totally Different Person", registrants, threshold=90)
        assert result is None

    def test_city_preference(self, registrants):
        result = match_payee_to_registrants("John Smith", registrants, city="Vancouver")
        assert result is not None
        assert result["city"] == "Vancouver"


class TestEntityResolution:
    def test_resolve_entities(self):
        payees = [{"payee_name": "Dr. John Smith", "city": "Vancouver", "amount_gross": 100000}]
        registrants = [
            {"full_name": "John Smith", "city": "Vancouver", "cpsbc_id": "C1", "specialty": "FM"},
        ]
        results = resolve_entities(payees, registrants, salt="test", threshold=70)
        assert len(results) == 1
        assert results[0]["entity_key_hash"]
        assert results[0]["matched_name"] == "John Smith"


class TestGeocoding:
    def test_city_centroid_fallback(self):
        result = _city_centroid_fallback("Vancouver")
        assert result["lat"] == pytest.approx(49.2827, abs=0.01)
        assert result["provider"] == "city_centroid"

    def test_unknown_city(self):
        result = _city_centroid_fallback("Narnia")
        assert result["lat"] is None

    def test_health_authority_lookup(self):
        assert _lookup_health_authority("Vancouver") == "Vancouver Coastal Health"
        assert _lookup_health_authority("Kelowna") == "Interior Health"
        assert _lookup_health_authority("Prince George") == "Northern Health"
        assert _lookup_health_authority("Victoria") == "Island Health"
        assert _lookup_health_authority("Surrey") == "Fraser Health"

    def test_bc_city_centroids_not_empty(self):
        assert len(BC_CITY_CENTROIDS) > 20


class TestBluebookParser:
    def test_extract_fiscal_year(self):
        assert extract_fiscal_year("bluebook-2022-2023.pdf") == "2022-2023"
        assert extract_fiscal_year("MSP_2021_2022.pdf") == "2021-2022"
        assert extract_fiscal_year("randomfile.pdf") is None

    def test_parse_row_valid(self):
        row = ["Dr. John Smith", "Family Medicine", "$350,000.00"]
        result = _parse_row(row, 0)
        assert result is not None
        assert result["payee_name"] == "Dr. John Smith"
        assert result["amount_gross"] == 350_000.00

    def test_parse_row_header(self):
        row = ["PAYEE NAME", "CATEGORY", "AMOUNT"]
        result = _parse_row(row, 0)
        assert result is None

    def test_parse_row_no_amount(self):
        row = ["Dr. John Smith", "No amount here"]
        result = _parse_row(row, 0)
        assert result is None
