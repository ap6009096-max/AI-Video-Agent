"""Tests for AnalyticsAgent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.analytics_agent import AnalyticsAgent
from config.settings import get_settings
from schemas.analytics import GeminiAnalyticsAnalysis, PREDICTION_DISCLAIMER
from schemas.job import FeatureFlags, SourceType, VideoJobConfig
from schemas.project import ProjectMetadata
from tools.analytics.catalog import clear_analytics_cache


def test_analytics_flag_off_skips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    clear_analytics_cache()
    project_dir = tmp_path / "outputs" / "projects" / "an1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="an1", source_type=SourceType.SCRIPT, raw_text="x"
    )
    result = AnalyticsAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(platform="YouTube"),
        features=FeatureFlags(analytics=False),
    )
    assert result.analytics_pack.plan.skipped is True
    data = json.loads(Path(result.analytics_path).read_text(encoding="utf-8"))
    assert data["plan"]["skipped"] is True
    assert PREDICTION_DISCLAIMER in data["plan"]["notes"]
    get_settings.cache_clear()


def test_analytics_writes_public_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    clear_analytics_cache()
    project_dir = tmp_path / "outputs" / "projects" / "an2"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="an2", source_type=SourceType.SCRIPT, raw_text="x"
    )

    def _fake(**_: object) -> GeminiAnalyticsAnalysis:
        return GeminiAnalyticsAnalysis(
            engagement_score=72.5,
            retention_score=68.0,
            shareability_score=80.0,
            watch_time_score=66.0,
            ctr_score=55.0,
            engagement_drivers=["hook"],
            retention_drivers=["pacing"],
            shareability_drivers=["emotion"],
            rationale="Solid short-form outlook.",
        )

    result = AnalyticsAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(platform="YouTube Shorts"),
        features=FeatureFlags(analytics=True),
        seo_pack={
            "plan": {
                "skipped": False,
                "title": "Short form tips",
                "description": "Grow faster",
                "tags": ["shorts"],
                "hashtags": ["#shorts"],
                "keywords": ["growth"],
            }
        },
        analyze_fn=_fake,
    )
    plan = result.analytics_pack.plan
    assert plan.skipped is False
    assert plan.engagement_score == 72.5
    assert plan.retention_score == 68.0
    assert plan.shareability_score == 80.0
    assert plan.watch_time_score == 66.0
    assert plan.ctr_score == 55.0
    assert PREDICTION_DISCLAIMER in plan.notes
    public = result.public_output()
    assert set(public.keys()) == {
        "engagement_score",
        "retention_score",
        "shareability_score",
    }
    get_settings.cache_clear()
