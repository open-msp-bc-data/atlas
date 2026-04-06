"""FastAPI application entry-point for MSP-BC Open Atlas."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from .database import init_db
from .routers import physicians, aggregations, admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Fail fast if the privacy salt is still the default placeholder
    from .config import get_privacy_config
    salt = os.environ.get("PRIVACY_SALT") or get_privacy_config().get("salt", "")
    if salt in ("", "CHANGE_ME_IN_PRODUCTION"):
        raise RuntimeError(
            "Privacy salt is not configured. Set PRIVACY_SALT env var or update "
            "privacy.salt in config.yaml before running in production."
        )
    yield


app = FastAPI(
    title="MSP-BC Open Atlas API",
    description="Privacy-safe geospatial API for British Columbia physician billing data.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS – restrict to known frontend origins (configurable via CORS_ORIGINS env var)
_cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://localhost:4173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins],
    allow_methods=["GET"],
    allow_headers=["X-Admin-Token"],
)

# Global per-IP rate limiter (120 req/min across all endpoints)
_global_rate_window = 60
_global_rate_max = 120
_global_rate_store: dict[str, list[float]] = {}

@app.middleware("http")
async def global_rate_limit(request: Request, call_next):
    import time
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    cutoff = now - _global_rate_window
    hits = _global_rate_store.get(client_ip, [])
    hits = [t for t in hits if t > cutoff]
    if len(hits) >= _global_rate_max:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
    hits.append(now)
    _global_rate_store[client_ip] = hits
    # Evict stale IPs periodically
    if len(_global_rate_store) > 10_000:
        stale = [k for k, v in _global_rate_store.items() if not v or v[-1] < cutoff]
        for k in stale:
            del _global_rate_store[k]
    return await call_next(request)

# CSP headers
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https://*.tile.openstreetmap.org; "
        "connect-src 'self'; "
        "font-src 'self'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response

# Routers
app.include_router(physicians.router)
app.include_router(aggregations.router)
app.include_router(admin.router)


@app.get("/health")
def health():
    return {"status": "ok"}


# Serve frontend static build if present
_frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
