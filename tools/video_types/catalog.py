"""Load and resolve video type presets from config/video_types.json."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from schemas.video_type import VideoTypePack, VideoTypePreset

_CATALOG_PATH = (
    Path(__file__).resolve().parent.parent.parent / "config" / "video_types.json"
)


def _norm(value: str) -> str:
    return " ".join((value or "").strip().lower().replace("_", " ").replace("-", " ").split())


@lru_cache(maxsize=1)
def _load_raw() -> list[dict[str, Any]]:
    return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))


def clear_video_type_cache() -> None:
    _load_raw.cache_clear()


def list_video_types() -> list[VideoTypePreset]:
    return [VideoTypePreset.model_validate(item) for item in _load_raw()]


def resolve_video_type(name_or_id: str) -> VideoTypePreset | None:
    key = _norm(name_or_id)
    if not key:
        return None
    for preset in list_video_types():
        if _norm(preset.id) == key or _norm(preset.name) == key:
            return preset
        for alias in preset.aliases:
            if _norm(alias) == key:
                return preset
    return None


def _fallback_preset(source_label: str) -> VideoTypePreset:
    return VideoTypePreset(
        id="fallback",
        name=source_label.strip() or "Shorts",
        aliases=[],
        aspect_ratio="9:16",
        pacing="medium",
        caption_style="clear burned-in captions",
        hook_strategy="open with the strongest grounded line from the content",
        visual_requirements="Platform-appropriate framing; keep subject readable on mobile",
        audio_requirements="Clear primary audio; light supportive music if needed",
        platform_compatibility=["YouTube Shorts", "TikTok", "Instagram Reels"],
        default_duration_sec=30,
        notes="Catalog miss — using soft fallback defaults.",
    )


def build_video_type_pack(
    video_type: str,
    *,
    platform: str = "",
) -> VideoTypePack:
    label = (video_type or "").strip() or "Shorts"
    preset = resolve_video_type(label)
    fallback = False
    notes = ""
    if preset is None:
        preset = _fallback_preset(label)
        fallback = True
        notes = f"Unknown video type '{label}'; used fallback defaults."
    else:
        notes = f"Resolved video type preset: {preset.name}"
        if platform and platform not in preset.platform_compatibility:
            notes += f" (platform '{platform}' not in preset compatibility list — guidance still applied)."
    return VideoTypePack(
        source_label=label,
        preset=preset,
        fallback=fallback,
        notes=notes,
    )


def video_type_prompt_block(pack: VideoTypePack) -> str:
    """Render a video type pack into prompt text for Gemini."""
    p = pack.preset
    lines = [
        f"Video type: {p.name} (source label: {pack.source_label})",
        f"Aspect ratio: {p.aspect_ratio}",
        f"Pacing: {p.pacing}",
        f"Caption style: {p.caption_style}",
        f"Hook strategy: {p.hook_strategy}",
        f"Visual requirements: {p.visual_requirements}",
        f"Audio requirements: {p.audio_requirements}",
        f"Platform compatibility: {', '.join(p.platform_compatibility)}",
        f"Default duration (sec): {p.default_duration_sec}",
    ]
    if p.notes:
        lines.append(f"Preset notes: {p.notes}")
    if pack.notes:
        lines.append(f"Resolve notes: {pack.notes}")
    return "\n".join(lines)
