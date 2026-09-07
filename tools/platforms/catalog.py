"""Load and resolve social platform presets from config/platforms.json."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from schemas.platform import PlatformPreset

_CATALOG_PATH = (
    Path(__file__).resolve().parent.parent.parent / "config" / "platforms.json"
)

REQUIRED_PLATFORM_NAMES = [
    "Instagram",
    "Instagram Reels",
    "Facebook",
    "YouTube",
    "YouTube Shorts",
    "TikTok",
    "X",
    "LinkedIn",
    "Pinterest",
    "Snapchat",
    "Reddit",
]


def _norm(value: str) -> str:
    return " ".join(
        (value or "").strip().lower().replace("_", " ").replace("-", " ").split()
    )


@lru_cache(maxsize=1)
def _load_raw() -> list[dict[str, Any]]:
    return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))


def clear_platform_cache() -> None:
    _load_raw.cache_clear()


def list_platforms() -> list[PlatformPreset]:
    return [PlatformPreset.model_validate(item) for item in _load_raw()]


def resolve_platform(name_or_id: str) -> PlatformPreset | None:
    key = _norm(name_or_id)
    if not key:
        return None
    for preset in list_platforms():
        if _norm(preset.id) == key or _norm(preset.name) == key:
            return preset
        for alias in preset.aliases:
            if _norm(alias) == key:
                return preset
    return None


def default_for_label(label: str) -> PlatformPreset:
    found = resolve_platform(label)
    if found:
        return found
    # Soft fallback: YouTube Shorts as product default
    return resolve_platform("YouTube Shorts") or list_platforms()[0]


def _fallback_preset(label: str) -> PlatformPreset:
    return PlatformPreset(
        id="fallback_shorts",
        name=label.strip() or "YouTube Shorts",
        official_url="https://www.youtube.com/shorts/",
        supported_aspect_ratios=["9:16"],
        caption_behavior="Captions preferred",
        cta_strategy="Soft engagement CTA",
        hook_style="Strong opening",
        pacing="fast",
        publish_enabled=False,
        notes="Unknown platform label — soft fallback to Shorts-like defaults.",
    )


def resolve_or_fallback(label: str) -> tuple[PlatformPreset, bool]:
    preset = resolve_platform(label)
    if preset is not None:
        # Hard guarantee
        preset.publish_enabled = False
        return preset, False
    fb = _fallback_preset(label)
    fb.publish_enabled = False
    return fb, True
