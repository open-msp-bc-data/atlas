"""SQLAlchemy ORM models for the MSP-BC Atlas."""

from __future__ import annotations

from sqlalchemy import Column, Float, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from .database import Base


class PhysicianRaw(Base):
    """Internal-only table with full physician details."""

    __tablename__ = "physicians_raw"

    id = Column(Integer, primary_key=True, autoincrement=True)
    full_name = Column(String, nullable=False)
    specialty = Column(String, nullable=True)
    address = Column(String, nullable=True)
    city = Column(String, nullable=True)
    health_authority = Column(String, nullable=True)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    license_status = Column(String, nullable=True)
    cpsbc_id = Column(String, nullable=True, unique=True)

    billings = relationship("Billing", back_populates="physician")
    public_record = relationship("PhysicianPublic", back_populates="physician", uselist=False)


class Billing(Base):
    """Billing records per physician per year."""

    __tablename__ = "billings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    physician_id = Column(Integer, ForeignKey("physicians_raw.id"), nullable=False)
    year = Column(String, nullable=False)  # e.g. "2022-2023"
    total_billings = Column(Float, nullable=False)

    physician = relationship("PhysicianRaw", back_populates="billings")


class PhysicianPublic(Base):
    """Privacy-safe public view of physicians."""

    __tablename__ = "physicians_public"

    id = Column(Integer, primary_key=True, autoincrement=True)
    physician_id = Column(Integer, ForeignKey("physicians_raw.id"), nullable=False, unique=True)
    pseudo_id = Column(String, nullable=False, unique=True)
    specialty = Column(String, nullable=True)
    specialty_group = Column(String, nullable=True)
    lat_approx = Column(Float, nullable=True)
    lng_approx = Column(Float, nullable=True)
    city = Column(String, nullable=True)
    health_authority = Column(String, nullable=True)

    physician = relationship("PhysicianRaw", back_populates="public_record")


class Aggregation(Base):
    """Pre-computed aggregations at various geographic levels."""

    __tablename__ = "aggregations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fiscal_year = Column(String, nullable=False)
    geo_level = Column(String, nullable=False)  # facility, city, ha
    geo_id = Column(String, nullable=False)
    geo_name = Column(String, nullable=False)
    specialty_group = Column(String, nullable=True)
    n_physicians = Column(Integer, nullable=False)
    total_payments = Column(Float, nullable=False)
    median_payments = Column(Float, nullable=True)
    pct_change_yoy = Column(Float, nullable=True)
    suppressed = Column(Boolean, default=False)
    suppression_reason = Column(String, nullable=True)
