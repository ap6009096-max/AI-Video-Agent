"""Tests for EnvironmentAgent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.environment_agent import EnvironmentAgent
from config.settings import get_settings
from schemas.job import SourceType, VideoJobConfig
from schemas.project import ProjectMetadata


def test_environment_agent_writes_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "env1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="env1", source_type=SourceType.SCRIPT, raw_text="x"
    )
    result = EnvironmentAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(environment="Foggy Forest"),
    )
    path = Path(result.environment_path)
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["preset"]["name"] == "Foggy Forest"
    assert data["plan"]["environment_name"] == "Foggy Forest"
    assert data["plan"]["summary"]
    assert data["fallback"] is False
    get_settings.cache_clear()


def test_environment_agent_unknown_soft_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "env2"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="env2", source_type=SourceType.SCRIPT, raw_text="x"
    )
    result = EnvironmentAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(environment="MadeUpRealm"),
    )
    assert result.environment_pack.fallback is True
    data = json.loads(Path(result.environment_path).read_text(encoding="utf-8"))
    assert data["fallback"] is True
    assert data["plan"]["summary"]
    get_settings.cache_clear()
