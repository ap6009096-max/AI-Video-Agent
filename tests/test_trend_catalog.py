"""Tests for trend catalog heuristics."""

from __future__ import annotations

from schemas.job import VideoJobConfig
from schemas.trend import GeminiTrendAnalysis
from tools.trend.catalog import (
    build_trend_pack,
    clear_trend_cache,
    list_trend_presets,
    resolve_trend_preset,
)


def test_list_six_platforms() -> None:
    clear_trend_cache()
    names = {str(p.get("name")) for p in list_trend_presets()}
    assert names == {
        "YouTube",
        "Instagram",
        "Facebook",
        "TikTok",
        "LinkedIn",
        "Pinterest",
    }


def test_resolve_aliases() -> None:
    clear_trend_cache()
    assert resolve_trend_preset("YouTube Shorts")["name"] == "YouTube"
    assert resolve_trend_preset("Instagram Reels")["name"] == "Instagram"
    assert resolve_trend_preset("Tik Tok")["name"] == "TikTok"


def test_heuristic_pack_without_gemini() -> None:
    clear_trend_cache()
    seo_pack = {
        "plan": {
            "skipped": False,
            "title": "Life hack tutorial",
            "description": "Must watch tips",
            "tags": ["hack", "tips"],
            "hashtags": ["#hack"],
            "keywords": ["tutorial"],
        }
    }
    pack = build_trend_pack(
        "TikTok",
        enabled=True,
        config=VideoJobConfig(platform="TikTok", audience="Gen Z"),
        seo_pack=seo_pack,
        analyze_fn=None,
    )
    # Without API key, should use heuristic (or gemini if key present — force heuristic via fake fail)
    assert pack.plan.skipped is False
    assert pack.plan.trend_score >= 0
    assert pack.plan.trend_topics
    assert pack.plan.recommended_tags
    assert pack.plan.trending_hashtags
    assert pack.plan.provider in {"heuristic", "gemini"}


def test_inject_analyze_fn() -> None:
    clear_trend_cache()

    def _fake(**_: object) -> GeminiTrendAnalysis:
        return GeminiTrendAnalysis(
            trend_score=88,
            trend_topics=["ai tools"],
            recommended_tags=["ai", "tools"],
            trending_hashtags=["#ai"],
            trending_keywords=["automation"],
            viral_patterns=["hook in 3 seconds"],
            audience_relevance="High for creators",
            topic_labels=["technology"],
        )

    pack = build_trend_pack(
        "YouTube",
        enabled=True,
        config=VideoJobConfig(platform="YouTube"),
        analyze_fn=_fake,
    )
    assert pack.plan.provider == "gemini"
    assert pack.plan.trend_score == 88.0
    assert pack.plan.trend_topics == ["ai tools"]
    assert "ai" in pack.plan.recommended_tags


def test_flag_off() -> None:
    clear_trend_cache()
    pack = build_trend_pack("YouTube", enabled=False)
    assert pack.plan.skipped is True
    assert pack.plan.trend_score == 0
    assert pack.plan.provider == "none"
