"""Competitor pack disk cache (7d TTL) + offline scaffold."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from tools.cache import cache_root, read_ttl_json, write_ttl_json

COMPETITOR_TTL_SECONDS = 7 * 24 * 60 * 60


def competitor_cache_path(
    niche_key: str, *, output_dir: str | None = None
) -> Path:
    safe = hashlib.sha256((niche_key or "general").encode("utf-8")).hexdigest()[:20]
    return cache_root(output_dir) / "competitors" / f"{safe}.json"


def load_cached_competitor(
    niche_key: str,
    *,
    output_dir: str | None = None,
    ttl_seconds: float = COMPETITOR_TTL_SECONDS,
) -> dict[str, Any] | None:
    path = competitor_cache_path(niche_key, output_dir=output_dir)
    payload = read_ttl_json(path, ttl_seconds=ttl_seconds)
    return payload if isinstance(payload, dict) else None


def store_cached_competitor(
    niche_key: str,
    pack: dict[str, Any],
    *,
    output_dir: str | None = None,
) -> Path:
    path = competitor_cache_path(niche_key, output_dir=output_dir)
    return write_ttl_json(path, pack)


def build_competitor_scaffold(
    *,
    niche: str = "",
    platform: str = "YouTube",
    topics: list[str] | None = None,
) -> dict[str, Any]:
    """Offline/heuristic competitor pack (no live scraping)."""
    topics = [t for t in (topics or []) if t][:8]
    niche_label = (niche or (topics[0] if topics else "general")).strip() or "general"
    seeds = topics or [niche_label]
    return {
        "niche": niche_label,
        "platform": platform or "YouTube",
        "source": "offline_scaffold",
        "ttl_days": 7,
        "competitors": [
            {
                "name": f"Peer channel — {seed}",
                "angle": f"Educational / entertainment hybrid on {seed}",
                "estimated_strength": "unknown",
                "notes": "Heuristic seed only — replace via PublishProvider plugin.",
            }
            for seed in seeds[:5]
        ],
        "gaps": [
            f"Underserved FAQ angles around {niche_label}",
            "Stronger thumbnail emotion vs peers",
            "Faster hook in first 3 seconds",
        ],
        "notes": (
            "Competitor pack is an offline scaffold with 7-day cache. "
            "Live fetch hooks live under plugins.PublishProvider."
        ),
        "raw": {"topics": seeds},
    }


def get_or_build_competitor_pack(
    *,
    niche: str = "",
    platform: str = "YouTube",
    topics: list[str] | None = None,
    output_dir: str | None = None,
) -> dict[str, Any]:
    key = json.dumps(
        {"niche": niche, "platform": platform, "topics": topics or []},
        sort_keys=True,
    )
    cached = load_cached_competitor(key, output_dir=output_dir)
    if cached is not None:
        cached = dict(cached)
        cached["cache_hit"] = True
        return cached
    pack = build_competitor_scaffold(
        niche=niche, platform=platform, topics=topics
    )
    store_cached_competitor(key, pack, output_dir=output_dir)
    pack = dict(pack)
    pack["cache_hit"] = False
    return pack
