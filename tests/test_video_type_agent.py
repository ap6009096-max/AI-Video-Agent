"""Tests for VideoTypeAgent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.video_type_agent import VideoTypeAgent
from config.settings import get_settings
from schemas.job import SourceType, VideoJobConfig
from schemas.project import ProjectMetadata


def test_video_type_agent_writes_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "vt1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="vt1", source_type=SourceType.SCRIPT, raw_text="x"
    )
    result = VideoTypeAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(video_type="Reels", platform="Instagram Reels"),
    )
    path = Path(result.video_type_path)
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["preset"]["name"] == "Reels"
    assert data["source_label"] == "Reels"
    assert data["fallback"] is False
    assert result.video_type_pack.preset.aspect_ratio == "9:16"
    get_settings.cache_clear()


def test_video_type_agent_unknown_soft_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "vt2"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="vt2", source_type=SourceType.SCRIPT, raw_text="x"
    )
    result = VideoTypeAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(video_type="MadeUpFormat"),
    )
    assert result.video_type_pack.fallback is True
    data = json.loads(Path(result.video_type_path).read_text(encoding="utf-8"))
    assert data["fallback"] is True
    assert data["preset"]["aspect_ratio"] == "9:16"
    get_settings.cache_clear()
