"""Tests for FunnyMomentAgent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.funny_moment_agent import FunnyMomentAgent
from config.settings import get_settings
from schemas.funny import FunnyMoment
from schemas.job import FeatureFlags, SourceType
from schemas.project import ProjectMetadata


def test_agent_writes_funny_moments_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "f1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(project_id="f1", source_type=SourceType.SCRIPT, raw_text="x")

    def _fake(**_kwargs):
        return [
            FunnyMoment(
                id=0,
                start=0.0,
                end=2.0,
                humor_kinds=["joke", "punchline"],
                humor_score=0.81,
                explanation="signals=transcript,timing; kinds=joke,punchline",
                transcript="To get to the other side!",
                suggested_title="Road joke",
                evidence=["transcript:joke_setup@0.0", "timing:punch_after_gap@1.5"],
            )
        ]

    result = FunnyMomentAgent(detect_fn=_fake).run(
        project,
        project_dir=project_dir,
        features=FeatureFlags(funny_moments=True, smart_clip_detection=True),
    )
    path = Path(result.funny_moments_path)
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["moments"][0]["humor_score"] == 0.81
    assert data["moments"][0]["suggested_title"] == "Road joke"
    assert "explanation" in data["moments"][0]
    assert data["summary"]["count"] == 1.0
    get_settings.cache_clear()


def test_flag_off_writes_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "f2"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(project_id="f2", source_type=SourceType.SCRIPT, raw_text="x")
    result = FunnyMomentAgent().run(
        project,
        project_dir=project_dir,
        features=FeatureFlags(funny_moments=False, smart_clip_detection=True),
    )
    assert result.funny_moments.moments == []
    assert result.funny_moments.provider == "disabled"
    assert Path(result.funny_moments_path).is_file()
    get_settings.cache_clear()
