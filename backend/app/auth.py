"""Shared authentication helpers."""

from __future__ import annotations

import hmac
import os

from .config import get_api_config


def validate_admin_token(token: str | None) -> bool:
    """Check if the provided token matches the configured admin token.

    Uses constant-time comparison to prevent timing attacks.
    Requires the configured token to be at least 16 characters.
    """
    if not token:
        return False
    expected = os.environ.get("ADMIN_TOKEN") or get_api_config().get("admin_token", "")
    expected = expected.strip()
    if not expected or len(expected) < 16:
        return False
    return hmac.compare_digest(token.strip(), expected)
