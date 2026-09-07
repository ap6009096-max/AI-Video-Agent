"""Disk cache helpers with TTL."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from core.logging import get_logger
from core.paths import ensure_output_dir

logger = get_logger(__name__)


def cache_root(output_dir: str | None = None) -> Path:
    root = ensure_output_dir(output_dir) / "cache"
    root.mkdir(parents=True, exist_ok=True)
    return root


def read_ttl_json(path: Path, *, ttl_seconds: float) -> Any | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("cache read failed %s: %s", path, exc)
        return None
    if not isinstance(raw, dict):
        return None
    ts = raw.get("_cached_at")
    try:
        cached_at = float(ts)
    except (TypeError, ValueError):
        return None
    if time.time() - cached_at > ttl_seconds:
        return None
    return raw.get("payload")


def write_ttl_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {"_cached_at": time.time(), "payload": payload}
    path.write_text(json.dumps(body, indent=2, default=str), encoding="utf-8")
    return path
