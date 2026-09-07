"""Tests for visual style catalog resolution and sanitization."""

from __future__ import annotations

from tools.visual_styles.catalog import (
    build_visual_style_pack,
    list_visual_styles,
    resolve_visual_style,
    sanitize_style_label,
    visual_style_prompt_block,
)


REQUIRED_NAMES = [
    "Anime",
    "Manga",
    "Hand-Painted Animation",
    "Stylized 3D Animation",
    "Watercolor",
    "Oil Painting",
    "Storybook",
    "Hand-Drawn 2D",
    "Paper Cutout",
    "Claymation",
    "Low-Poly 3D",
    "Voxel",
    "Comic Book",
    "Sketch",
    "Chibi",
    "Cyberpunk",
    "Steampunk",
    "Dark Fantasy",
    "Fairy-Tale Fantasy",
    "Photorealistic",
    "Cinematic",
    "Surreal",
    "Vintage Film",
]


def test_catalog_loads_all_twenty_three() -> None:
    types = list_visual_styles()
    names = {t.name for t in types}
    assert len(REQUIRED_NAMES) == 23
    missing = [n for n in REQUIRED_NAMES if n not in names]
    assert not missing, f"Missing presets: {missing}"
    assert len(types) == 23


def test_resolve_anime_cinematic_photorealistic() -> None:
    anime = resolve_visual_style("Anime")
    assert anime is not None
    assert anime.medium == "2d_animation"
    cine = resolve_visual_style("cinematic")
    assert cine is not None
    assert cine.name == "Cinematic"
    photo = resolve_visual_style("Photorealistic")
    assert photo is not None
    assert "natural" in photo.color_palette.lower() or photo.lighting


def test_legacy_minimal_to_sketch() -> None:
    preset = resolve_visual_style("Minimal")
    assert preset is not None
    assert preset.name == "Sketch"
    pack = build_visual_style_pack("Minimal")
    assert pack.fallback is False
    assert pack.preset.name == "Sketch"
    assert pack.plan.summary


def test_legacy_aliases() -> None:
    assert resolve_visual_style("Bold").name == "Comic Book"
    assert resolve_visual_style("Documentary").name == "Photorealistic"
    assert resolve_visual_style("Raw UGC").name == "Photorealistic"
    assert resolve_visual_style("Motion Graphic").name == "Stylized 3D Animation"


def test_studio_alias_sanitizes() -> None:
    preset, sanitized = sanitize_style_label("Pixar style")
    assert sanitized is True
    assert preset is not None
    assert preset.name == "Stylized 3D Animation"
    pack = build_visual_style_pack("Pixar style")
    assert pack.sanitized is True
    assert pack.preset.name == "Stylized 3D Animation"
    assert "generic" in pack.notes.lower() or "remapped" in pack.notes.lower()
    block = visual_style_prompt_block(pack)
    assert "Sanitized: yes" in block
    assert "Avoid:" in block


def test_unknown_soft_fallback() -> None:
    pack = build_visual_style_pack("Totally Unknown Style XYZ")
    assert pack.fallback is True
    assert pack.preset.medium == "photoreal"
    assert pack.plan.summary
    assert "Visual style:" in visual_style_prompt_block(pack)
