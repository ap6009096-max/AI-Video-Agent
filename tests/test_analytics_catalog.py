"""Tests for analytics catalog heuristics."""

from __future__ import annotations

from schemas.analytics import GeminiAnalyticsAnalysis, PREDICTION_DISCLAIMER
from schemas.job import VideoJobConfig
from tools.analytics.catalog import build_analytics_pack, clear_analytics_cache


def test_heuristic_pack_without_gemini() -> None:
    clear_analytics_cache()
    pack = build_analytics_pack(
        "TikTok",
        enabled=True,
        config=VideoJobConfig(platform="TikTok", audience="Gen Z"),
        seo_pack={
            "plan": {
                "skipped": False,
                "title": "Life hack tutorial",
                "description": "Must watch tips",
                "tags": ["hack", "tips"],
                "hashtags": ["#hack"],
                "keywords": ["tutorial"],
            }
        },
        trend_pack={"plan": {"skipped": False, "trend_score": 70}},
        thumbnail_pack={
            "plan": {
                "skipped": False,
                "thumbnail_text": "MUST WATCH",
                "emotion": "surprise",
                "layout": "face_left_text_right",
            }
        },
        viral_pack={"final_score": 0.8, "scores": {"shareability": 0.75}},
        analyze_fn=None,
    )
    assert pack.plan.skipped is False
    assert 0 <= pack.plan.engagement_score <= 100
    assert 0 <= pack.plan.retention_score <= 100
    assert 0 <= pack.plan.shareability_score <= 100
    assert 0 <= pack.plan.watch_time_score <= 100
    assert 0 <= pack.plan.ctr_score <= 100
    assert PREDICTION_DISCLAIMER in pack.plan.notes
    assert pack.plan.provider in {"heuristic", "gemini"}


def test_inject_analyze_fn() -> None:
    clear_analytics_cache()

    def _fake(**_: object) -> GeminiAnalyticsAnalysis:
        return GeminiAnalyticsAnalysis(
            engagement_score=81,
            retention_score=74,
            shareability_score=88,
            watch_time_score=70,
            ctr_score=65,
            engagement_drivers=["strong hook"],
            retention_drivers=["clear payoff"],
            shareability_drivers=["emotion"],
            rationale="Predicted from signals.",
        )

    pack = build_analytics_pack(
        "YouTube",
        enabled=True,
        config=VideoJobConfig(platform="YouTube"),
        analyze_fn=_fake,
    )
    assert pack.plan.provider == "gemini"
    assert pack.plan.engagement_score == 81.0
    assert pack.plan.retention_score == 74.0
    assert pack.plan.shareability_score == 88.0
    assert pack.plan.watch_time_score == 70.0
    assert pack.plan.ctr_score == 65.0


def test_flag_off() -> None:
    clear_analytics_cache()
    pack = build_analytics_pack("YouTube", enabled=False)
    assert pack.plan.skipped is True
    assert pack.plan.engagement_score == 0
    assert pack.plan.retention_score == 0
    assert pack.plan.shareability_score == 0
    assert pack.plan.provider == "none"
    assert PREDICTION_DISCLAIMER in pack.plan.notes


def test_scores_clamped() -> None:
    clear_analytics_cache()

    def _fake(**_: object) -> GeminiAnalyticsAnalysis:
        return GeminiAnalyticsAnalysis(
            engagement_score=150,
            retention_score=-10,
            shareability_score=1000,
            watch_time_score=50,
            ctr_score=50,
        )

    pack = build_analytics_pack(
        "YouTube",
        enabled=True,
        analyze_fn=_fake,
    )
    assert pack.plan.engagement_score == 100.0
    assert pack.plan.retention_score == 0.0
    assert pack.plan.shareability_score == 100.0
