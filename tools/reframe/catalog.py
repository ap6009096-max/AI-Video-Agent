"""Load reframe aspect presets and detection settings."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from schemas.reframe import AspectPreset

_CATALOG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "reframe.json"

SUPPORTED_ASPECTS = frozenset({"9:16", "1:1", "4:5"})


def _norm(value: str) -> str:
    return " ".join(
        (value or "").strip().lower().replace("_", " ").replace("-", ":").split()
    )


@lru_cache(maxsize=1)
def _load_raw() -> dict[str, Any]:
    return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))


def clear_reframe_cache() -> None:
    _load_raw.cache_clear()


def list_aspects() -> list[AspectPreset]:
    raw = _load_raw().get("aspects") or []
    return [AspectPreset.model_validate(item) for item in raw]


def detection_settings() -> dict[str, Any]:
    return dict(_load_raw().get("detection") or {})


def platform_defaults() -> dict[str, str]:
    raw = _load_raw().get("platform_defaults") or {}
    return {str(k): str(v) for k, v in raw.items()}


def resolve_aspect(name_or_id: str) -> AspectPreset | None:
    key = _norm(name_or_id).replace(" ", "")
    if not key:
        return None
    # Normalize "9 16" / "9:16"
    key = key.replace(" ", "")
    for preset in list_aspects():
        if _norm(preset.id).replace(" ", "") == key:
            return preset
        if _norm(preset.name).replace(" ", "") == key:
            return preset
        for alias in preset.aliases:
            if _norm(alias).replace(" ", "") == key or _norm(alias) == _norm(name_or_id):
                return preset
    # Direct ratio name match
    for preset in list_aspects():
        if preset.name.replace(" ", "") == name_or_id.strip().replace(" ", ""):
            return preset
    return None


def default_aspect_for_platform(platform: str) -> AspectPreset:
    defaults = platform_defaults()
    name = defaults.get(platform) or defaults.get(_norm(platform).title()) or "9:16"
    # Try exact platform key first
    for key, aspect_name in defaults.items():
        if _norm(key) == _norm(platform):
            name = aspect_name
            break
    return resolve_aspect(name) or list_aspects()[0]


def resolve_target_aspect(
    *,
    reframe_aspect: str = "",
    video_type_aspect: str = "",
    platform: str = "",
) -> AspectPreset:
    """Resolve order: explicit config → video type → platform default."""
    explicit = (reframe_aspect or "").strip()
    if explicit and explicit.lower() not in {"auto", ""}:
        found = resolve_aspect(explicit)
        if found:
            return found
    vt = (video_type_aspect or "").strip()
    if vt in SUPPORTED_ASPECTS or resolve_aspect(vt):
        found = resolve_aspect(vt)
        if found:
            return found
    return default_aspect_for_platform(platform or "YouTube Shorts")
