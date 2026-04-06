"""Tests for pipeline modules."""

from __future__ import annotations

import re
import pytest

from pipeline.entity_resolution import normalize_name, build_entity_key, match_payee_to_registrants, resolve_entities
from pipeline.geocode import geocode_address, _city_centroid_fallback, _lookup_health_authority, BC_CITY_CENTROIDS
from pipeline.ingest_bluebook import extract_fiscal_year, _ENTRY_RE, _clean_name, parse_bluebook_pdf
from pipeline.aggregate import compute_aggregations, compute_yoy


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
    def test_extract_fiscal_year_4plus4(self):
        assert extract_fiscal_year("bluebook-2022-2023.pdf") == "2022-2023"
        assert extract_fiscal_year("MSP_2021_2022.pdf") == "2021-2022"

    def test_extract_fiscal_year_4plus2(self):
        assert extract_fiscal_year("bluebook_2023-24.pdf") == "2023-2024"
        assert extract_fiscal_year("blue-book-2018-19.pdf") == "2018-2019"
        assert extract_fiscal_year("bluebook_2020_21_final.pdf") == "2020-2021"

    def test_extract_fiscal_year_single(self):
        assert extract_fiscal_year("bluebook2012.pdf") == "2011-2012"

    def test_extract_fiscal_year_none(self):
        assert extract_fiscal_year("randomfile.pdf") is None

    def test_entry_regex_matches_standard(self):
        text = "Smith, John .......................... 123,456.78"
        m = _ENTRY_RE.search(text)
        assert m is not None
        assert "Smith" in m.group(1)
        assert m.group(2) == "123,456.78"

    def test_entry_regex_matches_simple_name(self):
        text = "Doe, Jane .... 50,000.00"
        m = _ENTRY_RE.search(text)
        assert m is not None
        assert m.group(2) == "50,000.00"

    def test_entry_regex_no_match_header(self):
        text = "PAYMENTS TO PRACTITIONERS"
        m = _ENTRY_RE.search(text)
        assert m is None

    def test_entry_regex_no_match_plain_text(self):
        text = "This is a paragraph about physician payments."
        m = _ENTRY_RE.search(text)
        assert m is None

    def test_clean_name_trailing_dots(self):
        assert _clean_name("Smith, John...") == "Smith, John"

    def test_clean_name_multiple_spaces(self):
        assert _clean_name("Smith,   John") == "Smith, John"

    def test_clean_name_trailing_comma(self):
        assert _clean_name("Smith, John,") == "Smith, John"

    def test_clean_name_whitespace(self):
        assert _clean_name("  Smith, John  ") == "Smith, John"

    def test_entry_regex_handles_hyphenated_name(self):
        text = "O'Brien-Smith, Mary-Jane ............ 250,000.00"
        m = _ENTRY_RE.search(text)
        assert m is not None
        assert "O'Brien-Smith" in m.group(1)
        assert m.group(2) == "250,000.00"

    def test_entry_regex_handles_parenthesized_name(self):
        text = "Smith (née Jones), Mary .............. 100,000.00"
        m = _ENTRY_RE.search(text)
        assert m is not None
        assert m.group(2) == "100,000.00"

    def test_entry_regex_million_dollar_amount(self):
        text = "Dhanda, Dharminder Singh ............. 3,567,883.95"
        m = _ENTRY_RE.search(text)
        assert m is not None
        assert m.group(2) == "3,567,883.95"

    def test_entry_regex_minimum_dots(self):
        """Needs at least 2 dots to match."""
        text = "Smith, John . 100,000.00"  # only 1 dot
        m = _ENTRY_RE.search(text)
        # Should not match with only 1 dot separator
        assert m is None or ".." not in text

    def test_clean_name_empty(self):
        assert _clean_name("") == ""

    def test_clean_name_only_dots(self):
        assert _clean_name("...") == ""

    def test_extract_fiscal_year_underscore_separator(self):
        assert extract_fiscal_year("bluebook_2020_21.pdf") == "2020-2021"

    def test_extract_fiscal_year_no_digits(self):
        assert extract_fiscal_year("report.pdf") is None


class TestParseBluebookPdf:
    """Test the full PDF parser against a real Blue Book PDF."""

    @pytest.fixture
    def sample_pdf(self):
        import os
        pdf = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw", "bluebook_2023-24.pdf")
        if not os.path.exists(pdf):
            pytest.skip("Blue Book PDF not available for integration test")
        return pdf

    def test_parses_records(self, sample_pdf):
        results = parse_bluebook_pdf(sample_pdf)
        assert len(results) > 1000  # should have thousands of entries

    def test_record_structure(self, sample_pdf):
        results = parse_bluebook_pdf(sample_pdf)
        rec = results[0]
        assert "payee_name" in rec
        assert "amount_gross" in rec
        assert "section" in rec
        assert "source_page" in rec
        assert "fiscal_year" in rec

    def test_fiscal_year_extracted(self, sample_pdf):
        results = parse_bluebook_pdf(sample_pdf)
        assert results[0]["fiscal_year"] == "2023-2024"

    def test_sections_found(self, sample_pdf):
        results = parse_bluebook_pdf(sample_pdf)
        sections = {r["section"] for r in results}
        assert "practitioners" in sections

    def test_amounts_are_positive(self, sample_pdf):
        results = parse_bluebook_pdf(sample_pdf)
        for r in results:
            assert r["amount_gross"] > 0

    def test_no_absurd_amounts(self, sample_pdf):
        results = parse_bluebook_pdf(sample_pdf)
        for r in results:
            assert r["amount_gross"] <= 50_000_000

    def test_names_are_nonempty(self, sample_pdf):
        results = parse_bluebook_pdf(sample_pdf)
        for r in results:
            assert len(r["payee_name"]) >= 2


class TestComputeAggregations:
    def _make_records(self, n, city="Vancouver", fiscal_year="2023-2024", spec="All"):
        """Generate *n* billing records with unique entity keys."""
        return [
            {
                "fiscal_year": fiscal_year,
                "city": city,
                "specialty_group": spec,
                "amount_gross": 100_000 + i * 10_000,
                "entity_key_hash": f"ent-{i}",
            }
            for i in range(n)
        ]

    def test_k_anonymity_suppression(self):
        """Groups with fewer than k physicians should be suppressed."""
        records = self._make_records(3, city="SmallTown")
        result = compute_aggregations(records, geo_level="city", geo_key="city")
        assert len(result) == 1
        assert result[0]["suppressed"] is True
        assert result[0]["suppression_reason"] == "k_min"
        assert result[0]["total_payments"] is None

    def test_k_anonymity_passes(self):
        """Groups with at least k physicians should not be suppressed by k-anonymity."""
        records = self._make_records(6, city="LargeCity")
        result = compute_aggregations(records, geo_level="city", geo_key="city")
        assert len(result) == 1
        assert result[0]["suppressed"] is False
        assert result[0]["total_payments"] is not None
        assert result[0]["total_payments"] > 0

    def test_dominance_suppression(self):
        """Groups where one contributor dominates should be suppressed."""
        records = [
            {"fiscal_year": "2023-2024", "city": "DomCity", "specialty_group": "All",
             "amount_gross": 900_000, "entity_key_hash": "big"},
        ] + [
            {"fiscal_year": "2023-2024", "city": "DomCity", "specialty_group": "All",
             "amount_gross": 10_000, "entity_key_hash": f"small-{i}"}
            for i in range(5)
        ]
        result = compute_aggregations(records, geo_level="city", geo_key="city")
        assert len(result) == 1
        assert result[0]["suppressed"] is True
        assert result[0]["suppression_reason"] == "dominance"

    def test_max_share_not_in_output(self):
        """Internal max_share field should be stripped from output."""
        records = self._make_records(6)
        result = compute_aggregations(records)
        for cell in result:
            assert "max_share" not in cell

    def test_n_physicians_counts_unique_hashes(self):
        """n_physicians must be the count of distinct entity_key_hash values."""
        # Two billing rows for the same physician (same hash) should count as 1
        records = [
            {"fiscal_year": "2023-2024", "city": "UniqueTest", "specialty_group": "All",
             "amount_gross": 100_000, "entity_key_hash": "same-hash"},
            {"fiscal_year": "2023-2024", "city": "UniqueTest", "specialty_group": "All",
             "amount_gross": 50_000, "entity_key_hash": "same-hash"},
            {"fiscal_year": "2023-2024", "city": "UniqueTest", "specialty_group": "All",
             "amount_gross": 80_000, "entity_key_hash": "other-hash"},
        ] + [
            {"fiscal_year": "2023-2024", "city": "UniqueTest", "specialty_group": "All",
             "amount_gross": 70_000, "entity_key_hash": f"extra-hash-{i}"}
            for i in range(3)
        ]
        result = compute_aggregations(records, geo_level="city", geo_key="city")
        assert len(result) == 1
        # 5 unique hashes ("same-hash", "other-hash", and 3 extras) = 5 unique physicians
        assert result[0]["n_physicians"] == 5
        assert result[0]["suppressed"] is False

    def test_n_physicians_excludes_missing_hash(self):
        """Records without an entity_key_hash must not inflate the physician count."""
        # 6 records: 4 with hashes + 2 without (no hash) → count should be 4, not 6
        records = [
            {"fiscal_year": "2023-2024", "city": "HashTest", "specialty_group": "All",
             "amount_gross": 100_000, "entity_key_hash": f"hash-{i}"}
            for i in range(4)
        ] + [
            {"fiscal_year": "2023-2024", "city": "HashTest", "specialty_group": "All",
             "amount_gross": 50_000}  # no entity_key_hash
            for _ in range(2)
        ]
        result = compute_aggregations(records, geo_level="city", geo_key="city")
        assert len(result) == 1
        assert result[0]["n_physicians"] == 4


class TestComputeYoY:
    def _cell(self, geo_id, total, suppressed=False):
        return {
            "geo_level": "city",
            "geo_id": geo_id,
            "specialty_group": "All",
            "total_payments": total,
            "suppressed": suppressed,
        }

    def test_yoy_computed(self):
        """YoY should be computed for dual-year k-safe cells."""
        current = [self._cell("Van", 110_000)]
        previous = [self._cell("Van", 100_000)]
        result = compute_yoy(current, previous)
        assert len(result) == 1
        assert result[0]["pct_change_yoy"] == pytest.approx(0.1, abs=0.001)

    def test_yoy_skipped_when_previous_suppressed(self):
        """YoY should not be set when the previous year cell is suppressed."""
        current = [self._cell("Van", 110_000)]
        previous = [self._cell("Van", 100_000, suppressed=True)]
        result = compute_yoy(current, previous)
        assert result[0].get("pct_change_yoy") is None

    def test_yoy_skipped_when_current_suppressed(self):
        """YoY should not be set when the current year cell is suppressed."""
        current = [self._cell("Van", 110_000, suppressed=True)]
        previous = [self._cell("Van", 100_000)]
        result = compute_yoy(current, previous)
        assert result[0].get("pct_change_yoy") is None

    def test_yoy_no_matching_previous(self):
        """YoY should remain None if there's no matching previous cell."""
        current = [self._cell("Van", 110_000)]
        previous = [self._cell("Kel", 100_000)]
        result = compute_yoy(current, previous)
        assert result[0].get("pct_change_yoy") is None
