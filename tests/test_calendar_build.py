"""Tests for content calendar pack builder."""

from __future__ import annotations

from datetime import date

import pytest

from config.settings import get_settings
from schemas.calendar import GeminiCalendarBatch
from schemas.job import VideoJobConfig
from tools.calendar.build import build_calendar_pack


@pytest.fixture(autouse=True)
def _clear_settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("CALENDAR_HORIZON_DAYS", raising=False)
    monkeypatch.delenv("CALENDAR_POSTS_PER_WEEK", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_build_entries_have_required_keys() -> None:
    pack = build_calendar_pack(
        enabled=True,
        config=VideoJobConfig(platform="YouTube", video_type="Shorts"),
        script_pack={"primary": {"title": "Sleep tips", "hook": "Rest better"}},
        anchor_date=date(2026, 9, 1),
        horizon_days=7,
        posts_per_week=7,
    )
    assert pack.plan.skipped is False
    assert pack.plan.entries
    for entry in pack.plan.entries:
        data = entry.model_dump()
        assert set(data.keys()) == {"date", "topic", "platform", "video_type"}
        assert data["date"]
        assert data["topic"]
        assert data["platform"] == "YouTube"
        assert data["video_type"] == "Shorts"


def test_daily_weekly_monthly_grouping() -> None:
    pack = build_calendar_pack(
        enabled=True,
        config=VideoJobConfig(platform="TikTok", video_type="Reels"),
        research_report={"topic": "Focus habits", "outline": [{"heading": "Deep work"}]},
        trend_pack={"plan": {"trend_topics": ["productivity"]}},
        anchor_date=date(2026, 9, 1),
        horizon_days=14,
        posts_per_week=7,
    )
    assert pack.plan.daily
    assert pack.plan.weekly
    assert pack.plan.monthly
    # All flat entries appear in daily view
    daily_count = sum(len(d.entries) for d in pack.plan.daily)
    assert daily_count == len(pack.plan.entries)
    assert pack.plan.monthly[0].month.startswith("2026-09")


def test_skipped_empty() -> None:
    pack = build_calendar_pack(
        enabled=False,
        config=VideoJobConfig(platform="YouTube"),
        anchor_date=date(2026, 9, 1),
    )
    assert pack.plan.skipped is True
    assert pack.plan.entries == []
    assert pack.plan.daily == []
    assert pack.plan.weekly == []
    assert pack.plan.monthly == []
    assert pack.plan.provider == "none"


def test_horizon_respects_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CALENDAR_HORIZON_DAYS", "10")
    monkeypatch.setenv("CALENDAR_POSTS_PER_WEEK", "7")
    get_settings.cache_clear()
    pack = build_calendar_pack(
        enabled=True,
        config=VideoJobConfig(),
        anchor_date=date(2026, 1, 5),
    )
    assert pack.plan.horizon_days == 10
    assert pack.plan.anchor_date == "2026-01-05"
    assert len(pack.plan.entries) == 10


def test_enrich_fn_injection() -> None:
    def _enrich(**_: object) -> GeminiCalendarBatch:
        return GeminiCalendarBatch(topics=["A", "B", "C"], notes="test enrich")

    pack = build_calendar_pack(
        enabled=True,
        config=VideoJobConfig(platform="YouTube"),
        enrich_fn=_enrich,
        anchor_date=date(2026, 3, 1),
        horizon_days=3,
        posts_per_week=7,
    )
    assert pack.plan.provider == "gemini"
    assert pack.plan.entries[0].topic == "A"
    assert "test enrich" in pack.plan.notes
