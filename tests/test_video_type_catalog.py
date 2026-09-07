"""Tests for video type catalog resolution."""

from __future__ import annotations

from tools.video_types.catalog import (
    build_video_type_pack,
    list_video_types,
    resolve_video_type,
    video_type_prompt_block,
)


REQUIRED_NAMES = [
    "Reels",
    "Shorts",
    "Explainer",
    "Educational",
    "Talking Head",
    "Vlog",
    "Cinematic",
    "Storytelling",
    "Documentary",
    "Interview",
    "Podcast",
    "Reaction",
    "Review",
    "Unboxing",
    "Comparison",
    "News",
    "Motivational",
    "Faceless",
    "Screen Recording",
    "Animation",
    "Motion Graphics",
    "Whiteboard",
    "AI Avatar",
    "Kinetic Typography",
    "Montage",
    "B-Roll",
    "Before/After",
    "Case Study",
    "Testimonial",
    "Advertisement",
    "UGC",
    "Live Stream",
    "Gaming",
    "Travel",
    "Fitness",
    "Comedy",
    "Meme",
    "POV",
    "Day-in-the-Life",
    "Behind-the-Scenes",
]


def test_catalog_loads_all_forty() -> None:
    types = list_video_types()
    names = {t.name for t in types}
    assert len(REQUIRED_NAMES) == 40
    missing = [n for n in REQUIRED_NAMES if n not in names]
    assert not missing, f"Missing presets: {missing}"
    assert len(types) >= 40


def test_resolve_reels_shorts_documentary() -> None:
    reels = resolve_video_type("Reels")
    assert reels is not None
    assert reels.aspect_ratio == "9:16"
    shorts = resolve_video_type("shorts")
    assert shorts is not None
    assert shorts.name == "Shorts"
    doc = resolve_video_type("Documentary")
    assert doc is not None
    assert doc.pacing in {"slow", "medium", "fast"} or doc.pacing


def test_alias_short_form_to_shorts() -> None:
    preset = resolve_video_type("Short-form")
    assert preset is not None
    assert preset.name == "Shorts"
    pack = build_video_type_pack("Short-form")
    assert pack.fallback is False
    assert pack.preset.name == "Shorts"


def test_legacy_aliases() -> None:
    assert resolve_video_type("Tutorial") is not None
    assert resolve_video_type("Tutorial").name == "Educational"
    assert resolve_video_type("Promo").name == "Advertisement"
    assert resolve_video_type("Story").name == "Storytelling"
    assert resolve_video_type("Long-form").name == "Long-form"


def test_unknown_soft_fallback() -> None:
    pack = build_video_type_pack("Totally Unknown Type XYZ")
    assert pack.fallback is True
    assert pack.preset.aspect_ratio == "9:16"
    assert pack.preset.pacing == "medium"
    block = video_type_prompt_block(pack)
    assert "Video type:" in block
    assert "Aspect ratio:" in block
