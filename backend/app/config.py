"""Application configuration loaded from config.yaml.

Configuration is loaded once and cached for the process lifetime. Changes to
config.yaml require a full application restart to take effect. In multi-worker
deployments (e.g. gunicorn), each worker caches its own copy independently.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


_CONFIG_CACHE: dict[str, Any] | None = None
_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Load and cache YAML configuration."""
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None and path is None:
        return _CONFIG_CACHE

    config_path = path or Path(os.environ.get("APP_CONFIG", str(_CONFIG_PATH)))
    with open(config_path) as fh:
        cfg = yaml.safe_load(fh)
    if path is None:
        _CONFIG_CACHE = cfg
    return cfg


def get_privacy_config() -> dict[str, Any]:
    return load_config()["privacy"]


def get_db_url() -> str:
    return load_config()["database"]["url"]


def get_api_config() -> dict[str, Any]:
    return load_config()["api"]
