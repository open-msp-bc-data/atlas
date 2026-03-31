"""SQLAlchemy database setup."""

from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker, declarative_base

from .config import get_db_url

Base = declarative_base()

_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(get_db_url(), connect_args={"check_same_thread": False})
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)
    return _SessionLocal


def get_db() -> Session:  # type: ignore[misc]
    """FastAPI dependency that yields a database session."""
    session_factory = get_session_factory()
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


def _migrate_aggregation_unique_constraint(engine) -> None:
    """Idempotent migration: deduplicate aggregations and add the unique index.

    ``Base.metadata.create_all()`` only enforces constraints on *new* tables.
    This function handles already-initialized databases by:
    1. Deleting duplicate (fiscal_year, geo_level, geo_id, specialty_group) rows,
       keeping the row with the lowest ``id`` for each group.
    2. Creating the unique index if it does not already exist.

    It is safe to call multiple times (the CREATE INDEX uses IF NOT EXISTS).
    """
    with engine.begin() as conn:
        # Step 1 - remove duplicate rows, keeping the earliest (lowest id).
        # GROUP BY + MIN is straightforward and sufficient for the small aggregate
        # table produced by this pipeline (typically a few hundred rows).
        conn.execute(text(
            """
            DELETE FROM aggregations
            WHERE id NOT IN (
                SELECT MIN(id)
                FROM aggregations
                GROUP BY fiscal_year, geo_level, geo_id, specialty_group
            )
            """
        ))
        # Step 2 - create unique index if absent (SQLite & PostgreSQL both support
        # CREATE UNIQUE INDEX IF NOT EXISTS)
        conn.execute(text(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_aggregation_cell
            ON aggregations (fiscal_year, geo_level, geo_id, specialty_group)
            """
        ))


def init_db():
    """Create all tables and apply any pending lightweight migrations."""
    from . import models  # noqa: F401 – ensure models are imported
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    _migrate_aggregation_unique_constraint(engine)
