"""Tests for ReframeAgent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.reframe_agent import ReframeAgent
from config.settings import get_settings
from schemas.job import FeatureFlags, SourceType, VideoJobConfig
from schemas.project import ProjectMetadata


def test_reframe_agent_writes_plan_without_media(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "rf1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="rf1", source_type=SourceType.SCRIPT, raw_text="x"
    )
    result = ReframeAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(reframe_aspect="9:16", platform="TikTok"),
        features=FeatureFlags(smart_reframing=True),
        analysis={"properties": {"width": 1920, "height": 1080, "duration_seconds": 5}},
        clips={"clips": [{"id": 0, "start": 0.0, "end": 5.0}]},
    )
    path = Path(result.reframe_path)
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["plan"]["skipped"] is False
    assert data["plan"]["encoded"] is False
    assert data["plan"]["target_aspect"] == "9:16"
    assert data["plan"]["output_path"] == ""
    get_settings.cache_clear()


def test_reframe_agent_flag_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "rf2"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="rf2", source_type=SourceType.SCRIPT, raw_text="x"
    )
    result = ReframeAgent().run(
        project,
        project_dir=project_dir,
        features=FeatureFlags(smart_reframing=False),
    )
    assert result.reframe_pack.plan.skipped is True
    assert result.reframe_pack.plan.encoded is False
    get_settings.cache_clear()


def test_reframe_plan_before_encode_honesty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "rf3"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="rf3", source_type=SourceType.UPLOAD, source_path=""
    )
    result = ReframeAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(reframe_aspect="1:1"),
        features=FeatureFlags(smart_reframing=True),
        video_type_pack={"preset": {"aspect_ratio": "9:16"}},
    )
    # Explicit reframe_aspect wins
    assert result.reframe_pack.plan.target_aspect == "1:1"
    assert Path(result.reframe_path).is_file()
    # Never claim encode without file
    assert not (
        result.reframe_pack.plan.encoded
        and not result.reframe_pack.plan.output_path
    )
    get_settings.cache_clear()
