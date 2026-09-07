"""Tests for caption style / platform safe-area catalog."""

from __future__ import annotations

from tools.captions.catalog import (
    clear_caption_cache,
    list_caption_styles,
    list_platform_safe_areas,
    resolve_caption_style,
    resolve_safe_area,
)


def test_catalog_loads_styles() -> None:
    clear_caption_cache()
    styles = list_caption_styles()
    names = {s.name for s in styles}
    for required in (
        "Platform Safe",
        "Minimal",
        "Pop",
        "Kinetic",
        "High Contrast",
        "TikTok",
        "Shorts",
        "Reels",
        "Podcast",
        "Gaming",
        "Educational",
    ):
        assert required in names


def test_catalog_loads_platforms() -> None:
    clear_caption_cache()
    areas = list_platform_safe_areas()
    names = {a.name for a in areas}
    assert "YouTube Shorts" in names
    assert "TikTok" in names
    tiktok = resolve_safe_area("TikTok")
    assert tiktok is not None
    assert tiktok.margin_v >= 180


def test_resolve_caption_style() -> None:
    clear_caption_cache()
    kinetic = resolve_caption_style("Kinetic")
    assert kinetic is not None
    assert kinetic.animation == "word_highlight"
    safe = resolve_caption_style("platform safe")
    assert safe is not None
    assert safe.name == "Platform Safe"


def test_prompt29_style_effects() -> None:
    clear_caption_cache()
    tiktok = resolve_caption_style("TikTok")
    assert tiktok is not None
    assert "bounce" in tiktok.effects
    assert "word_highlight" in tiktok.effects
    shorts = resolve_caption_style("Shorts")
    assert shorts is not None
    assert "pop" in shorts.effects
    reels = resolve_caption_style("Reels")
    assert reels is not None
    assert "zoom" in reels.effects
    gaming = resolve_caption_style("Gaming")
    assert gaming is not None
    assert gaming.emoji_allowed is True
    podcast = resolve_caption_style("Podcast")
    assert podcast is not None
    assert podcast.animation == "none"
