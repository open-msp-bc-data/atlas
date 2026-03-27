"""SQLAlchemy database setup."""

from __future__ import annotations

from sqlalchemy import create_engine
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


def init_db():
    """Create all tables."""
    from . import models  # noqa: F401 – ensure models are imported
    Base.metadata.create_all(bind=get_engine())
