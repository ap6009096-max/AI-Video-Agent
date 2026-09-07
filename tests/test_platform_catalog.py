"""Tests for platforms catalog."""

from __future__ import annotations

from tools.platforms.catalog import (
    REQUIRED_PLATFORM_NAMES,
    list_platforms,
    resolve_platform,
)


def test_catalog_loads_required_platforms() -> None:
    platforms = list_platforms()
    names = {p.name for p in platforms}
    missing = [n for n in REQUIRED_PLATFORM_NAMES if n not in names]
    assert not missing, f"Missing platforms: {missing}"


def test_all_have_url_and_publish_disabled() -> None:
    for preset in list_platforms():
        assert preset.official_url.startswith("http")
        assert preset.publish_enabled is False
        assert preset.supported_aspect_ratios


def test_resolve_key_platforms() -> None:
    assert resolve_platform("TikTok") is not None
    assert resolve_platform("YouTube Shorts").name == "YouTube Shorts"
    assert resolve_platform("Twitter").name == "X"  # alias
    assert resolve_platform("Reddit").subreddit_dependent is True
    assert "2:3" in resolve_platform("Pinterest").supported_aspect_ratios
