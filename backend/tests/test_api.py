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


@pytest.fixture(autouse=True)
def setup_db():
    """Create tables and seed minimal data before each test."""
    # Import models to register them with Base metadata
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=TEST_ENGINE)
    db = TestSession()

    # Seed a physician
    phys = PhysicianRaw(
        full_name="Dr. Test Physician",
        specialty="Family Medicine",
        address="123 Test St",
        city="Vancouver",
        health_authority="Vancouver Coastal Health",
        lat=49.2827,
        lng=-123.1207,
        license_status="Active",
        cpsbc_id="CPSBC-99999",
    )
    db.add(phys)
    db.flush()

    # Billing records
    db.add(Billing(physician_id=phys.id, year="2022-2023", total_billings=300_000))
    db.add(Billing(physician_id=phys.id, year="2023-2024", total_billings=350_000))

    # Public record
    pseudo = deterministic_pseudo_id(phys.full_name, salt="msp-bc-atlas-default-salt")
    lat_a, lng_a = jitter_location(49.2827, -123.1207, seed=42)
    db.add(
        PhysicianPublic(
            physician_id=phys.id,
            pseudo_id=pseudo,
            specialty="Family Medicine",
            specialty_group="General Practice",
            lat_approx=lat_a,
            lng_approx=lng_a,
            city="Vancouver",
            health_authority="Vancouver Coastal Health",
        )
    )

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


class TestHeatmapEndpoint:
    def test_heatmap(self, client):
        resp = client.get("/heatmap")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
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

    def test_wrong_token_returns_403(self, client):
        resp = client.get("/admin/raw", headers={"x-admin-token": "wrong"})
        assert resp.status_code == 403

    def test_valid_token(self, client):
        resp = client.get("/admin/raw", headers={"x-admin-token": "change-me-in-production"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert "full_name" in data[0]  # admin CAN see raw data


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
