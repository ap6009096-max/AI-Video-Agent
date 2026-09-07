"""Load caption styles, platform safe areas, and keyword/emoji rules."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from schemas.captions import CaptionStylePreset, PlatformSafeArea

_CATALOG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "captions.json"


def _norm(value: str) -> str:
    return " ".join(
        (value or "").strip().lower().replace("_", " ").replace("-", " ").split()
    )


@lru_cache(maxsize=1)
def _load_raw() -> dict[str, Any]:
    return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))


def clear_caption_cache() -> None:
    _load_raw.cache_clear()


def list_caption_styles() -> list[CaptionStylePreset]:
    raw = _load_raw().get("styles") or []
    return [CaptionStylePreset.model_validate(item) for item in raw]


def list_platform_safe_areas() -> list[PlatformSafeArea]:
    raw = _load_raw().get("platforms") or []
    return [PlatformSafeArea.model_validate(item) for item in raw]


def keyword_stopwords() -> set[str]:
    return {str(w).lower() for w in (_load_raw().get("keyword_stopwords") or [])}


def keyword_boost() -> set[str]:
    return {str(w).lower() for w in (_load_raw().get("keyword_boost") or [])}


def emoji_map() -> dict[str, str]:
    raw = _load_raw().get("emoji_map") or {}
    return {str(k).lower(): str(v) for k, v in raw.items()}


def resolve_caption_style(name_or_id: str) -> CaptionStylePreset | None:
    key = _norm(name_or_id)
    if not key:
        return None
    for preset in list_caption_styles():
        if _norm(preset.id) == key or _norm(preset.name) == key:
            return preset
        for alias in preset.aliases:
            if _norm(alias) == key:
                return preset
    return None


def resolve_safe_area(platform: str) -> PlatformSafeArea | None:
    key = _norm(platform)
    if not key:
        return None
    for area in list_platform_safe_areas():
        if _norm(area.id) == key or _norm(area.name) == key:
            return area
        for alias in area.aliases:
            if _norm(alias) == key:
                return area
    return None


def default_caption_style() -> CaptionStylePreset:
    return resolve_caption_style("Platform Safe") or CaptionStylePreset(
        id="platform_safe",
        name="Platform Safe",
    )


def default_safe_area() -> PlatformSafeArea:
    return resolve_safe_area("YouTube Shorts") or PlatformSafeArea(
        id="youtube_shorts",
        name="YouTube Shorts",
        margin_v=180,
    )
