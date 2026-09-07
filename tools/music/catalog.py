"""Load and resolve music presets from config/music.json."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from schemas.av_plan import MusicPack, MusicPlan, MusicPreset

_CATALOG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "music.json"


def _norm(value: str) -> str:
    return " ".join(
        (value or "").strip().lower().replace("_", " ").replace("-", " ").split()
    )


@lru_cache(maxsize=1)
def _load_raw() -> list[dict[str, Any]]:
    return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))


def clear_music_cache() -> None:
    _load_raw.cache_clear()


def list_music_presets() -> list[MusicPreset]:
    return [MusicPreset.model_validate(item) for item in _load_raw()]


def resolve_music(name_or_id: str) -> MusicPreset | None:
    key = _norm(name_or_id)
    if not key:
        return None
    for preset in list_music_presets():
        if _norm(preset.id) == key or _norm(preset.name) == key:
            return preset
        for alias in preset.aliases:
            if _norm(alias) == key:
                return preset
    return None


def _fallback_preset(label: str) -> MusicPreset:
    return MusicPreset(
        id="fallback_original",
        name=label.strip() or "Original Audio",
        mode="original",
        mood="original",
        energy="source",
        notes="Unknown music label — falling back to original audio.",
        generation_required=False,
    )


def build_music_pack(
    music_label: str,
    *,
    enabled: bool = True,
) -> MusicPack:
    label = (music_label or "").strip() or "Original Audio"
    preset = resolve_music(label)
    fallback = False
    if preset is None:
        preset = _fallback_preset(label)
        fallback = True

    skipped = False
    notes = f"Resolved music preset: {preset.name}"
    if not enabled:
        # Feature off → treat as original / no replacement
        skipped = True
        notes = "Music feature flag off — keeping original audio (no bed planned)."
        preset = resolve_music("Original Audio") or _fallback_preset("Original Audio")

    plan = MusicPlan(
        preset_name=preset.name,
        mode=preset.mode,
        mood=preset.mood,
        energy=preset.energy,
        generation_required=False,  # MVP: never require generation
        asset_path="",
        skipped=skipped,
        notes=notes if enabled else notes,
    )
    if enabled and not skipped:
        plan.notes = (
            f"{notes}. Selection/plan only — music generation not required for MVP."
        )
    return MusicPack(
        source_label=label,
        preset=preset,
        plan=plan,
        fallback=fallback,
        notes=plan.notes,
    )
