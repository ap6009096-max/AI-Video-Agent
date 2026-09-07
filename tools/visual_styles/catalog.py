"""Load and resolve visual style presets from config/visual_styles.json."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from schemas.visual_style import VisualStylePack, VisualStylePlan, VisualStylePreset

_CATALOG_PATH = (
    Path(__file__).resolve().parent.parent.parent / "config" / "visual_styles.json"
)

# Normalized phrases that indicate studio/artist clone requests.
# These must also appear as aliases (or names) on generic presets.
_SANITIZE_PHRASES: frozenset[str] = frozenset(
    {
        "studio ghibli",
        "ghibli",
        "ghibli style",
        "miyazaki",
        "miyazaki style",
        "disney",
        "disney style",
        "pixar",
        "pixar style",
        "dreamworks",
        "dreamworks style",
        "marvel comic",
        "dc comic",
        "in the style of",
        "style of",
    }
)

_ARTIST_LIKE = re.compile(
    r"\b(style of|in the style of|like\s+\w+\s+studio|studio\s+\w+|artist)\b",
    re.I,
)


def _norm(value: str) -> str:
    return " ".join(
        (value or "").strip().lower().replace("_", " ").replace("-", " ").split()
    )


@lru_cache(maxsize=1)
def _load_raw() -> list[dict[str, Any]]:
    return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))


def clear_visual_style_cache() -> None:
    _load_raw.cache_clear()


def list_visual_styles() -> list[VisualStylePreset]:
    return [VisualStylePreset.model_validate(item) for item in _load_raw()]


def resolve_visual_style(name_or_id: str) -> VisualStylePreset | None:
    key = _norm(name_or_id)
    if not key:
        return None
    for preset in list_visual_styles():
        if _norm(preset.id) == key or _norm(preset.name) == key:
            return preset
        for alias in preset.aliases:
            if _norm(alias) == key:
                return preset
    return None


def sanitize_style_label(label: str) -> tuple[VisualStylePreset | None, bool]:
    """
    Resolve a label, marking sanitized=True when it matches studio/artist phrases.

    Returns (preset_or_None, sanitized).
    """
    key = _norm(label)
    if not key:
        return None, False

    # Explicit sanitize phrases → prefer generic remap via aliases on presets.
    # Extra remap targets for phrases not stored as JSON aliases:
    phrase_targets: dict[str, str] = {
        "studio ghibli": "Hand-Painted Animation",
        "ghibli": "Hand-Painted Animation",
        "ghibli style": "Hand-Painted Animation",
        "miyazaki": "Hand-Painted Animation",
        "miyazaki style": "Hand-Painted Animation",
        "disney": "Fairy-Tale Fantasy",
        "disney style": "Fairy-Tale Fantasy",
        "pixar": "Stylized 3D Animation",
        "pixar style": "Stylized 3D Animation",
        "dreamworks": "Stylized 3D Animation",
        "dreamworks style": "Stylized 3D Animation",
        "marvel comic": "Comic Book",
        "dc comic": "Comic Book",
    }
    if key in phrase_targets:
        preset = resolve_visual_style(phrase_targets[key])
        return preset, True

    if key in _SANITIZE_PHRASES or key.startswith("in the style of") or key.startswith(
        "style of"
    ):
        # Generic artist-request wording without a named target → storybook-safe default
        preset = resolve_visual_style("Storybook")
        return preset, True

    preset = resolve_visual_style(label)
    if preset is not None:
        # Matched via an alias that is also a sanitize phrase
        for alias in preset.aliases:
            if _norm(alias) == key and key in _SANITIZE_PHRASES:
                return preset, True
        return preset, False

    if _ARTIST_LIKE.search(label or ""):
        # Unknown artist/studio-like request → soft generic remap later
        return None, True

    return None, False


def build_visual_style_plan(preset: VisualStylePreset) -> VisualStylePlan:
    summary = (
        f"{preset.name}: {preset.medium} look with {preset.color_palette}; "
        f"lighting — {preset.lighting}."
    )
    return VisualStylePlan(
        style_name=preset.name,
        medium=preset.medium,
        line_quality=preset.line_quality,
        shading=preset.shading,
        color_palette=preset.color_palette,
        lighting=preset.lighting,
        texture=preset.texture,
        camera_motion=preset.camera_motion,
        composition=preset.composition,
        motion_feel=preset.motion_feel,
        render_notes=preset.render_notes,
        avoid=preset.avoid,
        summary=summary,
    )


def _fallback_preset(source_label: str) -> VisualStylePreset:
    return VisualStylePreset(
        id="fallback",
        name=source_label.strip() or "Photorealistic",
        aliases=[],
        medium="photoreal",
        line_quality="photographic; no drawn outline",
        shading="physically based; natural contrast",
        color_palette="naturalistic; subtle grade",
        lighting="real-world motivated light",
        texture="accurate materials",
        camera_motion="stable or natural handheld",
        composition="clear subject framing",
        motion_feel="real-world timing",
        render_notes="Use generic photoreal characteristics only.",
        avoid=(
            "Do not imitate a living artist or copyrighted studio look; "
            "describe traits only."
        ),
        notes="Catalog miss — using soft photorealistic fallback defaults.",
    )


def build_visual_style_pack(visual_style: str) -> VisualStylePack:
    label = (visual_style or "").strip() or "Cinematic"
    preset, sanitized = sanitize_style_label(label)
    fallback = False
    notes = ""

    if preset is None and sanitized:
        preset = _fallback_preset(label)
        fallback = True
        notes = (
            f"Artist/studio-like request '{label}' converted to generic "
            "visual characteristics (photorealistic fallback)."
        )
        sanitized = True
    elif preset is None:
        preset = _fallback_preset(label)
        fallback = True
        notes = f"Unknown visual style '{label}'; used photorealistic fallback defaults."
    elif sanitized:
        notes = (
            f"Request '{label}' remapped to generic preset '{preset.name}' "
            "(no living-artist or studio clone)."
        )
    else:
        notes = f"Resolved visual style preset: {preset.name}"

    plan = build_visual_style_plan(preset)
    return VisualStylePack(
        source_label=label,
        preset=preset,
        plan=plan,
        sanitized=sanitized,
        fallback=fallback,
        notes=notes,
    )


def visual_style_prompt_block(pack: VisualStylePack) -> str:
    """Render a visual style pack into prompt text for Gemini."""
    p = pack.preset
    plan = pack.plan
    lines = [
        f"Visual style: {p.name} (source label: {pack.source_label})",
        f"Plan summary: {plan.summary}",
        f"Medium: {p.medium}",
        f"Line quality: {p.line_quality}",
        f"Shading: {p.shading}",
        f"Color palette: {p.color_palette}",
        f"Lighting: {p.lighting}",
        f"Texture: {p.texture}",
        f"Camera motion: {p.camera_motion}",
        f"Composition: {p.composition}",
        f"Motion feel: {p.motion_feel}",
        f"Render notes: {p.render_notes}",
        f"Avoid: {p.avoid}",
    ]
    if p.notes:
        lines.append(f"Preset notes: {p.notes}")
    if pack.sanitized:
        lines.append("Sanitized: yes — use generic characteristics only.")
    if pack.notes:
        lines.append(f"Resolve notes: {pack.notes}")
    return "\n".join(lines)
