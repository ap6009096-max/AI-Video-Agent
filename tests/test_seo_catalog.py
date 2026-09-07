"""Tests for SEO catalog."""

from __future__ import annotations

from schemas.job import VideoJobConfig
from tools.seo.catalog import (
    build_seo_pack,
    clear_seo_cache,
    list_seo_presets,
    resolve_seo,
)


def test_list_six_platforms() -> None:
    clear_seo_cache()
    names = {p.name for p in list_seo_presets()}
    assert names == {
        "YouTube",
        "Instagram",
        "Facebook",
        "TikTok",
        "LinkedIn",
        "Pinterest",
    }


def test_resolve_aliases() -> None:
    clear_seo_cache()
    assert resolve_seo("YouTube Shorts").name == "YouTube"
    assert resolve_seo("Instagram Reels").name == "Instagram"
    assert resolve_seo("Tik Tok").name == "TikTok"
    assert resolve_seo("Linked In").name == "LinkedIn"
    assert resolve_seo("Pin").name == "Pinterest"


def test_build_pack_has_keywords_hashtags_tags() -> None:
    clear_seo_cache()
    platform_pack = {
        "plan": {
            "metadata": {
                "title": "Forest Survival Secrets",
                "description": "Learn three tips for hiking safely.",
                "tags": ["hiking", "forest"],
                "hashtags": ["#hiking", "#outdoors"],
                "keywords": ["survival", "trail"],
            }
        }
    }
    pack = build_seo_pack(
        "LinkedIn",
        enabled=True,
        config=VideoJobConfig(platform="LinkedIn"),
        platform_pack=platform_pack,
    )
    assert pack.plan.skipped is False
    assert pack.plan.platform == "LinkedIn"
    assert pack.plan.title == "Forest Survival Secrets"
    assert "hiking" in " ".join(pack.plan.tags).lower() or pack.plan.tags
    assert all(h.startswith("#") for h in pack.plan.hashtags)
    assert pack.plan.keywords
    assert len(pack.plan.hashtags) >= 2


def test_build_pack_flag_off() -> None:
    clear_seo_cache()
    pack = build_seo_pack("YouTube", enabled=False)
    assert pack.plan.skipped is True
    assert pack.plan.title == ""
    assert pack.plan.hashtags == []
