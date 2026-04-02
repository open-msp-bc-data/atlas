"""FastAPI application entry-point for MSP-BC Open Atlas."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
    allow_headers=["*"],
)

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
