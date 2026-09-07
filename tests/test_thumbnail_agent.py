"""Tests for ThumbnailAgent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.thumbnail_agent import ThumbnailAgent
from config.settings import get_settings
from schemas.job import FeatureFlags, SourceType, VideoJobConfig
from schemas.project import ProjectMetadata
from tools.thumbnail.catalog import clear_thumbnail_cache


def test_thumbnail_flag_off_skips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    clear_thumbnail_cache()
    project_dir = tmp_path / "outputs" / "projects" / "th1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="th1", source_type=SourceType.SCRIPT, raw_text="x"
    )
    result = ThumbnailAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(platform="YouTube"),
        features=FeatureFlags(thumbnail=False),
    )
    assert result.thumbnail_pack.plan.skipped is True
    data = json.loads(Path(result.thumbnail_path).read_text(encoding="utf-8"))
    assert data["plan"]["skipped"] is True
    get_settings.cache_clear()


def test_thumbnail_writes_public_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    clear_thumbnail_cache()
    project_dir = tmp_path / "outputs" / "projects" / "th2"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="th2", source_type=SourceType.SCRIPT, raw_text="x"
    )
    platform_pack = {
        "plan": {
            "metadata": {
                "title": "Click This Now",
                "hook": "The twist will shock you",
                "thumbnail_text": "SHOCK",
            }
        }
    }
    result = ThumbnailAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(
            platform="YouTube Shorts",
            thumbnail_platform="YouTube",
            voice_emotion="curious",
        ),
        features=FeatureFlags(thumbnail=True),
        platform_pack=platform_pack,
    )
    plan = result.thumbnail_pack.plan
    assert plan.skipped is False
    assert plan.platform == "YouTube"
    assert plan.title == "Click This Now"
    assert plan.hook == "The twist will shock you"
    assert plan.thumbnail_text == "SHOCK"
    assert plan.layout
    assert plan.face_placement
    assert plan.click_titles
    public = result.public_output()
    assert set(public.keys()) == {
        "title",
        "hook",
        "thumbnail_text",
        "emotion",
        "layout",
    }
    data = json.loads(Path(result.thumbnail_path).read_text(encoding="utf-8"))
    assert data["plan"]["face_placement"]
    get_settings.cache_clear()
