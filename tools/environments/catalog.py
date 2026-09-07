"""Load and resolve environment presets from config/environments.json."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from schemas.environment import EnvironmentPack, EnvironmentPlan, EnvironmentPreset

_CATALOG_PATH = (
    Path(__file__).resolve().parent.parent.parent / "config" / "environments.json"
)


def _norm(value: str) -> str:
    return " ".join(
        (value or "").strip().lower().replace("_", " ").replace("-", " ").split()
    )


@lru_cache(maxsize=1)
def _load_raw() -> list[dict[str, Any]]:
    return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))


def clear_environment_cache() -> None:
    _load_raw.cache_clear()


def list_environments() -> list[EnvironmentPreset]:
    return [EnvironmentPreset.model_validate(item) for item in _load_raw()]


def resolve_environment(name_or_id: str) -> EnvironmentPreset | None:
    key = _norm(name_or_id)
    if not key:
        return None
    for preset in list_environments():
        if _norm(preset.id) == key or _norm(preset.name) == key:
            return preset
        for alias in preset.aliases:
            if _norm(alias) == key:
                return preset
    return None


def build_environment_plan(preset: EnvironmentPreset) -> EnvironmentPlan:
    summary = (
        f"{preset.name}: {preset.visual_description} "
        f"Lighting — {preset.lighting}. Atmosphere — {preset.color_atmosphere}."
    )
    return EnvironmentPlan(
        environment_name=preset.name,
        visual_description=preset.visual_description,
        lighting=preset.lighting,
        color_atmosphere=preset.color_atmosphere,
        camera_suggestions=preset.camera_suggestions,
        background_requirements=preset.background_requirements,
        broll_requirements=preset.broll_requirements,
        transition_suggestions=preset.transition_suggestions,
        summary=summary,
    )


def _fallback_preset(source_label: str) -> EnvironmentPreset:
    return EnvironmentPreset(
        id="fallback",
        name=source_label.strip() or "Wildlife/Nature Forest",
        aliases=[],
        visual_description=(
            "Natural realistic forest habitat with believable flora and depth"
        ),
        lighting="Natural daylight through canopy; soft fill from sky",
        color_atmosphere="True-to-life greens and browns; calm nature feel",
        camera_suggestions="Observational framing; quiet walk-through; patient wides",
        background_requirements="Natural forest without fantasy props",
        broll_requirements="Leaf litter, streams, wind in trees, wildlife cues if available",
        transition_suggestions="Natural hard cuts; soft dissolves; match-cut on motion",
        notes="Catalog miss — using soft Wildlife/Nature Forest–like fallback defaults.",
    )


def build_environment_pack(environment: str) -> EnvironmentPack:
    label = (environment or "").strip() or "Wildlife/Nature Forest"
    preset = resolve_environment(label)
    fallback = False
    if preset is None:
        preset = _fallback_preset(label)
        fallback = True
        notes = (
            f"Unknown environment '{label}'; used Wildlife/Nature Forest–like fallback."
        )
    else:
        notes = f"Resolved environment preset: {preset.name}"
    plan = build_environment_plan(preset)
    return EnvironmentPack(
        source_label=label,
        preset=preset,
        plan=plan,
        fallback=fallback,
        notes=notes,
    )


def environment_prompt_block(pack: EnvironmentPack) -> str:
    """Render an environment pack into prompt text for Gemini."""
    p = pack.preset
    plan = pack.plan
    lines = [
        f"Environment: {p.name} (source label: {pack.source_label})",
        f"Plan summary: {plan.summary}",
        f"Visual description: {p.visual_description}",
        f"Lighting: {p.lighting}",
        f"Color / atmosphere: {p.color_atmosphere}",
        f"Camera suggestions: {p.camera_suggestions}",
        f"Background requirements: {p.background_requirements}",
        f"B-roll requirements: {p.broll_requirements}",
        f"Transition suggestions: {p.transition_suggestions}",
    ]
    if p.notes:
        lines.append(f"Preset notes: {p.notes}")
    if pack.notes:
        lines.append(f"Resolve notes: {pack.notes}")
    return "\n".join(lines)
