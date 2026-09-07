"""Tests for thumbnail catalog."""

from __future__ import annotations

from schemas.job import VideoJobConfig
from tools.thumbnail.catalog import (
    build_thumbnail_pack,
    clear_thumbnail_cache,
    list_thumbnails,
    resolve_thumbnail,
)


def test_list_four_platforms() -> None:
    clear_thumbnail_cache()
    names = {p.name for p in list_thumbnails()}
    assert names == {"YouTube", "Instagram", "Facebook", "TikTok"}


def test_resolve_aliases() -> None:
    clear_thumbnail_cache()
    assert resolve_thumbnail("YouTube Shorts") is not None
    assert resolve_thumbnail("YouTube Shorts").name == "YouTube"
    assert resolve_thumbnail("Instagram Reels").name == "Instagram"
    assert resolve_thumbnail("Tik Tok").name == "TikTok"
    assert resolve_thumbnail("FB").name == "Facebook"


def test_build_pack_from_platform_metadata() -> None:
    clear_thumbnail_cache()
    platform_pack = {
        "plan": {
            "metadata": {
                "title": "Secret Forest Trick",
                "hook": "Nobody expected this",
                "thumbnail_text": "SECRET",
            }
        }
    }
    pack = build_thumbnail_pack(
        "TikTok",
        enabled=True,
        config=VideoJobConfig(platform="TikTok", voice_emotion="excited"),
        platform_pack=platform_pack,
    )
    assert pack.plan.skipped is False
    assert pack.plan.platform == "TikTok"
    assert pack.plan.title == "Secret Forest Trick"
    assert pack.plan.hook == "Nobody expected this"
    assert pack.plan.thumbnail_text == "SECRET"
    assert pack.plan.layout == "bold_center_face_upper"
    assert pack.plan.face_placement
    assert len(pack.plan.click_titles) >= 2
    assert pack.plan.emotion == "excited"


def test_build_pack_flag_off() -> None:
    clear_thumbnail_cache()
    pack = build_thumbnail_pack("YouTube", enabled=False)
    assert pack.plan.skipped is True
    assert pack.plan.title == ""
