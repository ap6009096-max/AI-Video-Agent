"""Trend pack disk cache (24h TTL)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from tools.cache import cache_root, read_ttl_json, write_ttl_json

TREND_TTL_SECONDS = 24 * 60 * 60


def _trend_cache_key(
    platform_label: str,
    *,
    script_pack: dict[str, Any] | None,
    seo_pack: dict[str, Any] | None,
) -> str:
    blob = {
        "platform": (platform_label or "").strip().lower(),
        "script": (script_pack or {}).get("plan") if isinstance(script_pack, dict) else None,
        "seo_title": (
            ((seo_pack or {}).get("plan") or {}).get("title")
            if isinstance(seo_pack, dict)
            else None
        ),
    }
    digest = hashlib.sha256(
        json.dumps(blob, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]
    return digest


def trend_cache_path(
    platform_label: str,
    *,
    script_pack: dict[str, Any] | None = None,
    seo_pack: dict[str, Any] | None = None,
    output_dir: str | None = None,
) -> Path:
    key = _trend_cache_key(
        platform_label, script_pack=script_pack, seo_pack=seo_pack
    )
    return cache_root(output_dir) / "trends" / f"{key}.json"


def load_cached_trend(
    platform_label: str,
    *,
    script_pack: dict[str, Any] | None = None,
    seo_pack: dict[str, Any] | None = None,
    output_dir: str | None = None,
    ttl_seconds: float = TREND_TTL_SECONDS,
) -> dict[str, Any] | None:
    path = trend_cache_path(
        platform_label,
        script_pack=script_pack,
        seo_pack=seo_pack,
        output_dir=output_dir,
    )
    payload = read_ttl_json(path, ttl_seconds=ttl_seconds)
    return payload if isinstance(payload, dict) else None


def store_cached_trend(
    platform_label: str,
    pack: dict[str, Any],
    *,
    script_pack: dict[str, Any] | None = None,
    seo_pack: dict[str, Any] | None = None,
    output_dir: str | None = None,
) -> Path:
    path = trend_cache_path(
        platform_label,
        script_pack=script_pack,
        seo_pack=seo_pack,
        output_dir=output_dir,
    )
    return write_ttl_json(path, pack)
