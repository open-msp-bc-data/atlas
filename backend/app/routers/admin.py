"""Admin-only endpoints – protected by token, exposes raw data."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from ..auth import validate_admin_token
from ..database import get_db
from ..models import PhysicianRaw
from ..schemas import PhysicianRawOut

router = APIRouter(prefix="/admin", tags=["admin"])


def _verify_admin_token(x_admin_token: str = Header(...)):
    """Dependency that validates the admin bearer token."""
    if not validate_admin_token(x_admin_token):
        raise HTTPException(status_code=403, detail="Invalid admin token")


@router.get("/raw", response_model=list[PhysicianRawOut], dependencies=[Depends(_verify_admin_token)])
def list_raw_physicians(
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Admin endpoint: return raw physician records (names, exact addresses)."""
    return db.query(PhysicianRaw).offset(offset).limit(limit).all()
