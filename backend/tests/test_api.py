"""Tests for the FastAPI endpoints."""

from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Point to config for testing
os.environ["APP_CONFIG"] = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
# Set a valid privacy salt so the app starts
os.environ["PRIVACY_SALT"] = "test-salt-for-ci-runs"

from app.database import Base, get_db
from app.models import PhysicianRaw, Billing, PhysicianPublic, Aggregation
from app.privacy import deterministic_pseudo_id, jitter_location


# ── Test DB fixture ───────────────────────────────────────────────────
# StaticPool ensures all connections share the same in-memory database
TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(bind=TEST_ENGINE, autoflush=False, autocommit=False)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


def _seed_physicians(db, count, city="Vancouver", specialty="Family Medicine",
                     health_authority="Vancouver Coastal Health"):
    """Seed multiple physicians for k-anonymity testing."""
    records = []
    for i in range(count):
        name = f"Dr. Test Physician {city} {i}"
        phys = PhysicianRaw(
            full_name=name,
            specialty=specialty,
            address=f"{i} Test St",
            city=city,
            health_authority=health_authority,
            lat=49.2827 + i * 0.001,
            lng=-123.1207 + i * 0.001,
            license_status="Active",
            cpsbc_id=f"CPSBC-{city}-{i}",
        )
        db.add(phys)
        db.flush()

        pseudo = deterministic_pseudo_id(name, city=city, salt="msp-bc-atlas-default-salt")
        lat_a, lng_a = jitter_location(phys.lat, phys.lng, seed=42 + i)
        pub = PhysicianPublic(
            physician_id=phys.id,
            pseudo_id=pseudo,
            specialty=specialty,
            specialty_group="General Practice",
            lat_approx=lat_a,
            lng_approx=lng_a,
            city=city,
            health_authority=health_authority,
        )
        db.add(pub)
        db.flush()

        db.add(Billing(physician_id=phys.id, year="2022-2023", total_billings=300_000 + i * 10_000))
        db.add(Billing(physician_id=phys.id, year="2023-2024", total_billings=350_000 + i * 10_000))
        records.append(pub)
    return records


@pytest.fixture(autouse=True)
def setup_db():
    """Create tables and seed minimal data before each test."""
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=TEST_ENGINE)
    db = TestSession()

    # Seed 6 physicians in Vancouver (above k_min=5)
    _seed_physicians(db, 6, city="Vancouver")

    # Seed 2 physicians in SmallTown (below k_min=5)
    _seed_physicians(db, 2, city="SmallTown", health_authority="Northern Health")

    # Aggregation
    db.add(
        Aggregation(
            fiscal_year="2023-2024",
            geo_level="city",
            geo_id="vancouver",
            geo_name="Vancouver",
            specialty_group="All",
            n_physicians=50,
            total_payments=15_000_000,
            median_payments=300_000,
            pct_change_yoy=0.05,
            suppressed=False,
        )
    )
    db.add(
        Aggregation(
            fiscal_year="2023-2024",
            geo_level="city",
            geo_id="small_town",
            geo_name="Small Town",
            specialty_group="All",
            n_physicians=2,
            total_payments=0,
            median_payments=None,
            suppressed=True,
            suppression_reason="k_min",
        )
    )

    db.commit()
    db.close()

    yield

    Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture()
def client():
    """Create a fresh test client with dependency overrides."""
    from app.main import app

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


class TestHealthEndpoint:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestPhysiciansEndpoint:
    def test_list_physicians(self, client):
        resp = client.get("/physicians")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        phys = data[0]
        assert phys["pseudo_id"].startswith("PHY-")
        assert "full_name" not in phys  # must not leak raw name
        assert "address" not in phys

    def test_filter_by_city(self, client):
        resp = client.get("/physicians", params={"city": "Vancouver"})
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_filter_by_nonexistent_city(self, client):
        resp = client.get("/physicians", params={"city": "Atlantis"})
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_k_anonymity_suppression(self, client):
        """Filtering to a small group should return suppression notice."""
        resp = client.get("/physicians", params={"city": "SmallTown"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["suppressed"] is True
        assert data["reason"] == "query_k_anonymity"

    def test_k_anonymity_no_count_leak(self, client):
        """Suppression response must NOT include the exact count."""
        resp = client.get("/physicians", params={"city": "SmallTown"})
        data = resp.json()
        assert "n_matching" not in data

    def test_k_anonymity_off_without_token(self, client):
        """k_anonymity=off without admin token should still enforce suppression."""
        resp = client.get("/physicians", params={"city": "SmallTown", "k_anonymity": "off"})
        data = resp.json()
        assert data["suppressed"] is True

    def test_k_anonymity_admin_bypass(self, client, monkeypatch):
        """Admin with valid token can bypass k-anonymity."""
        monkeypatch.setenv("ADMIN_TOKEN", "test-admin-token-1234567890")
        resp = client.get(
            "/physicians",
            params={"city": "SmallTown", "k_anonymity": "off"},
            headers={"x-admin-token": "test-admin-token-1234567890"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2


class TestHeatmapEndpoint:
    def test_heatmap(self, client):
        resp = client.get("/heatmap")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_heatmap_has_n_physicians(self, client):
        resp = client.get("/heatmap")
        data = resp.json()
        if len(data) > 0:
            assert "n_physicians" in data[0]
            assert "lat" in data[0]
            assert "lng" in data[0]
            assert "intensity" in data[0]


class TestAggregationsEndpoint:
    def test_list_aggregations(self, client):
        resp = client.get("/aggregations")
        assert resp.status_code == 200
        data = resp.json()
        # Suppressed should be hidden by default
        assert all(not item["suppressed"] for item in data)

    def test_include_suppressed(self, client):
        resp = client.get("/aggregations", params={"include_suppressed": True})
        assert resp.status_code == 200
        data = resp.json()
        assert any(item["suppressed"] for item in data)

    def test_filter_by_geo_level(self, client):
        resp = client.get("/aggregations", params={"geo_level": "city"})
        assert resp.status_code == 200


class TestAdminEndpoint:
    def test_no_token_returns_422(self, client):
        resp = client.get("/admin/raw")
        assert resp.status_code == 422

    def test_wrong_token_returns_403(self, client, monkeypatch):
        monkeypatch.setenv("ADMIN_TOKEN", "test-secret-token-1234567890")
        resp = client.get("/admin/raw", headers={"x-admin-token": "wrong"})
        assert resp.status_code == 403

    def test_valid_token(self, client, monkeypatch):
        monkeypatch.setenv("ADMIN_TOKEN", "test-secret-token-1234567890")
        resp = client.get("/admin/raw", headers={"x-admin-token": "test-secret-token-1234567890"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert "full_name" in data[0]  # admin CAN see raw data

    def test_short_token_rejected(self, client, monkeypatch):
        """Tokens shorter than 16 chars should be rejected."""
        monkeypatch.setenv("ADMIN_TOKEN", "short")
        resp = client.get("/admin/raw", headers={"x-admin-token": "short"})
        assert resp.status_code == 403


class TestTrendsEndpoint:
    def test_trend_not_found(self, client):
        resp = client.get("/trends/PHY-NONEXIST")
        assert resp.status_code == 404

    def test_trend_found(self, client):
        # Get the pseudo_id from the physicians list first
        physicians = client.get("/physicians").json()
        pseudo_id = physicians[0]["pseudo_id"]
        resp = client.get(f"/trends/{pseudo_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pseudo_id"] == pseudo_id
        assert len(data["data"]) == 2
