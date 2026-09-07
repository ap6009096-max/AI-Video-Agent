"""Tests for TrendAgent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.trend_agent import TrendAgent
from config.settings import get_settings
from schemas.job import FeatureFlags, SourceType, VideoJobConfig
from schemas.project import ProjectMetadata
from schemas.trend import GeminiTrendAnalysis
from tools.trend.catalog import clear_trend_cache


def test_trend_flag_off_skips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    clear_trend_cache()
    project_dir = tmp_path / "outputs" / "projects" / "tr1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="tr1", source_type=SourceType.SCRIPT, raw_text="x"
    )
    result = TrendAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(platform="YouTube"),
        features=FeatureFlags(trend=False),
    )
    assert result.trend_pack.plan.skipped is True
    data = json.loads(Path(result.trend_path).read_text(encoding="utf-8"))
    assert data["plan"]["skipped"] is True
    get_settings.cache_clear()


def test_trend_writes_public_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    clear_trend_cache()
    project_dir = tmp_path / "outputs" / "projects" / "tr2"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="tr2", source_type=SourceType.SCRIPT, raw_text="x"
    )

    def _fake(**_: object) -> GeminiTrendAnalysis:
        return GeminiTrendAnalysis(
            trend_score=72.5,
            trend_topics=["short form tips", "fyp"],
            recommended_tags=["shorts", "tips"],
            trending_hashtags=["#shorts"],
            trending_keywords=["viral"],
            viral_patterns=["pattern interrupt"],
            audience_relevance="Strong for Shorts",
            topic_labels=["education"],
        )

    result = TrendAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(platform="YouTube Shorts"),
        features=FeatureFlags(trend=True),
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
    plan = result.trend_pack.plan
    assert plan.skipped is False
    assert plan.trend_score == 72.5
    assert plan.trend_topics
    assert plan.recommended_tags
    public = result.public_output()
    assert set(public.keys()) == {
        "trend_score",
        "trend_topics",
        "recommended_tags",
    }
    get_settings.cache_clear()
