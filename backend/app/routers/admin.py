"""Admin-only endpoints – protected by token, exposes raw data."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.orm import Session

from ..auth import validate_admin_token
from ..database import get_db
from ..models import PhysicianRaw
from ..schemas import PhysicianRawOut

router = APIRouter(prefix="/admin", tags=["admin"])
_audit_log = logging.getLogger("admin.audit")


def _verify_admin_token(x_admin_token: str = Header(...)):
    """Dependency that validates the admin bearer token."""
    if not validate_admin_token(x_admin_token):
        raise HTTPException(status_code=403, detail="Invalid admin token")


@router.get("/raw", response_model=list[PhysicianRawOut], dependencies=[Depends(_verify_admin_token)])
def list_raw_physicians(
    request: Request,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    x_admin_token: str = Header(...),
    db: Session = Depends(get_db),
):
    """Admin endpoint: return raw physician records (names, exact addresses)."""
    token_fingerprint = hashlib.sha256(x_admin_token.encode()).hexdigest()[:8]
    _audit_log.warning(
        "admin_raw_access | ip=%s | token=%s | offset=%d | limit=%d | ts=%s",
        request.client.host if request.client else "unknown",
        token_fingerprint,
        offset,
        limit,
        datetime.now(timezone.utc).isoformat(),
    )
    return db.query(PhysicianRaw).offset(offset).limit(limit).all()
