"""Tests for repurpose catalog."""

from __future__ import annotations

from schemas.job import SourceType, VideoJobConfig
from schemas.repurpose import GeminiRepurposeBatch
from tools.repurpose.catalog import (
    build_repurpose_pack,
    clear_repurpose_cache,
    resolve_source_kind,
)


def test_resolve_source_kind_auto() -> None:
    clear_repurpose_cache()
    assert resolve_source_kind("", source_type=SourceType.YOUTUBE) == "video"
    assert resolve_source_kind("", source_type=SourceType.UPLOAD) == "video"
    assert resolve_source_kind("", source_type=SourceType.SCRIPT) == "transcript"
    assert resolve_source_kind("Podcast") == "podcast"
    assert resolve_source_kind("Article") == "article"


def test_heuristic_fills_all_formats() -> None:
    clear_repurpose_cache()
    pack = build_repurpose_pack(
        enabled=True,
        config=VideoJobConfig(platform="TikTok", audience="Gen Z"),
        source_type=SourceType.YOUTUBE,
        seo_pack={
            "plan": {
                "skipped": False,
                "title": "Forest tips",
                "description": "Three ways to hike safely. Stay hydrated.",
                "hashtags": ["#hiking"],
            }
        },
        analyze_fn=None,
    )
    assert pack.plan.skipped is False
    assert pack.plan.source_kind == "video"
    assert pack.plan.reels
    assert pack.plan.shorts
    assert pack.plan.tiktok
    assert pack.plan.blog_summary
    assert pack.plan.linkedin_post
    assert len(pack.plan.twitter_thread) >= 2
    assert pack.plan.instagram_caption
    assert pack.plan.newsletter_summary
    assert pack.plan.provider in {"heuristic", "gemini"}


def test_inject_analyze_fn() -> None:
    clear_repurpose_cache()

    def _fake(**_: object) -> GeminiRepurposeBatch:
        return GeminiRepurposeBatch(
            reels="R",
            shorts="S",
            tiktok="T",
            blog_summary="B",
            linkedin_post="L",
            twitter_thread=["1/ a", "2/ b"],
            instagram_caption="I",
            newsletter_summary="N",
        )

    pack = build_repurpose_pack(
        enabled=True,
        config=VideoJobConfig(repurpose_source="Podcast"),
        source_type=SourceType.SCRIPT,
        analyze_fn=_fake,
    )
    assert pack.plan.source_kind == "podcast"
    assert pack.plan.provider == "gemini"
    assert pack.plan.reels == "R"
    assert pack.plan.twitter_thread == ["1/ a", "2/ b"]


def test_flag_off() -> None:
    clear_repurpose_cache()
    pack = build_repurpose_pack(enabled=False)
    assert pack.plan.skipped is True
    assert pack.plan.provider == "none"
    assert pack.plan.reels == ""
