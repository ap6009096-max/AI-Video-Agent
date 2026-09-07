"""Tests for VisualStyleAgent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.visual_style_agent import VisualStyleAgent
from config.settings import get_settings
from schemas.job import SourceType, VideoJobConfig
from schemas.project import ProjectMetadata


def test_visual_style_agent_writes_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "vs1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="vs1", source_type=SourceType.SCRIPT, raw_text="x"
    )
    result = VisualStyleAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(visual_style="Anime"),
    )
    path = Path(result.visual_style_path)
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["preset"]["name"] == "Anime"
    assert data["plan"]["style_name"] == "Anime"
    assert data["plan"]["summary"]
    assert data["fallback"] is False
    assert result.visual_style_pack.plan.medium == "2d_animation"
    get_settings.cache_clear()


def test_visual_style_agent_unknown_soft_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "vs2"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="vs2", source_type=SourceType.SCRIPT, raw_text="x"
    )
    result = VisualStyleAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(visual_style="MadeUpLook"),
    )
    assert result.visual_style_pack.fallback is True
    data = json.loads(Path(result.visual_style_path).read_text(encoding="utf-8"))
    assert data["fallback"] is True
    assert data["plan"]["summary"]
    get_settings.cache_clear()
