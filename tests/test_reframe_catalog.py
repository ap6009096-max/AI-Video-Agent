"""Tests for reframe aspect catalog."""

from __future__ import annotations

from tools.reframe.catalog import (
    default_aspect_for_platform,
    list_aspects,
    resolve_aspect,
    resolve_target_aspect,
)


def test_catalog_loads_aspects() -> None:
    aspects = list_aspects()
    names = {a.name for a in aspects}
    assert names == {"9:16", "1:1", "4:5"}


def test_platform_defaults() -> None:
    assert default_aspect_for_platform("TikTok").name == "9:16"
    assert default_aspect_for_platform("LinkedIn").name == "1:1"
    assert default_aspect_for_platform("Instagram").name == "4:5"


def test_resolve_target_order() -> None:
    explicit = resolve_target_aspect(
        reframe_aspect="1:1",
        video_type_aspect="9:16",
        platform="TikTok",
    )
    assert explicit.name == "1:1"
    from_vt = resolve_target_aspect(
        reframe_aspect="",
        video_type_aspect="4:5",
        platform="TikTok",
    )
    assert from_vt.name == "4:5"
    assert resolve_aspect("9:16") is not None
