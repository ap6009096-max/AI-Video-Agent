"""Tests for SeoAgent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.seo_agent import SeoAgent
from config.settings import get_settings
from schemas.job import FeatureFlags, SourceType, VideoJobConfig
from schemas.project import ProjectMetadata
from tools.seo.catalog import clear_seo_cache


def test_seo_flag_off_skips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    clear_seo_cache()
    project_dir = tmp_path / "outputs" / "projects" / "seo1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="seo1", source_type=SourceType.SCRIPT, raw_text="x"
    )
    result = SeoAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(platform="YouTube"),
        features=FeatureFlags(seo=False),
    )
    assert result.seo_pack.plan.skipped is True
    data = json.loads(Path(result.seo_path).read_text(encoding="utf-8"))
    assert data["plan"]["skipped"] is True
    get_settings.cache_clear()


def test_seo_writes_public_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    clear_seo_cache()
    project_dir = tmp_path / "outputs" / "projects" / "seo2"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="seo2", source_type=SourceType.SCRIPT, raw_text="x"
    )
    platform_pack = {
        "plan": {
            "metadata": {
                "title": "Clickbait Free Tips",
                "description": "Honest advice for creators.",
                "tags": ["creators", "tips"],
                "hashtags": ["#creators"],
                "keywords": ["youtube", "growth"],
            }
        }
    }
    result = SeoAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(
            platform="YouTube Shorts",
            seo_platform="YouTube",
        ),
        features=FeatureFlags(seo=True),
        platform_pack=platform_pack,
    )
    plan = result.seo_pack.plan
    assert plan.skipped is False
    assert plan.platform == "YouTube"
    assert plan.title == "Clickbait Free Tips"
    assert plan.description
    assert plan.tags
    assert plan.hashtags
    assert plan.keywords
    public = result.public_output()
    assert set(public.keys()) == {
        "title",
        "description",
        "tags",
        "hashtags",
        "keywords",
    }
    get_settings.cache_clear()
