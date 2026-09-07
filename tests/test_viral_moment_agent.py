"""Tests for ViralMomentAgent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.viral_moment_agent import ViralMomentAgent
from config.settings import get_settings
from schemas.job import FeatureFlags, SourceType
from schemas.project import ProjectMetadata
from schemas.viral import ViralMoment, ViralScoreBreakdown
from tools.moments.viral_detect import DISCLAIMER


def test_agent_writes_viral_moments_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "v1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(project_id="v1", source_type=SourceType.SCRIPT, raw_text="x")

    def _fake(**_kwargs):
        return [
            ViralMoment(
                id=0,
                start=0.0,
                end=3.0,
                scores=ViralScoreBreakdown(
                    hook=0.8,
                    emotion=0.7,
                    shareability=0.6,
                    reasons={"hook": "hook=0.80: opener"},
                ),
                final_score=0.52,
                rank=1,
                explanation=f"{DISCLAIMER} Weighted final_score=0.52.",
                transcript="Why this changes everything",
                suggested_title="Why this changes everything",
                evidence=["seed:hook"],
            )
        ]

    result = ViralMomentAgent(detect_fn=_fake).run(
        project,
        project_dir=project_dir,
        features=FeatureFlags(viral_moments=True, smart_clip_detection=True),
    )
    path = Path(result.viral_moments_path)
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["moments"][0]["final_score"] == 0.52
    assert data["moments"][0]["rank"] == 1
    assert "scores" in data["moments"][0]
    assert "guarantee" in data["notes"].lower() or "heuristic" in data["notes"].lower()
    assert data["summary"]["count"] == 1.0
    get_settings.cache_clear()


def test_flag_off_writes_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "v2"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(project_id="v2", source_type=SourceType.SCRIPT, raw_text="x")
    result = ViralMomentAgent().run(
        project,
        project_dir=project_dir,
        features=FeatureFlags(viral_moments=False, smart_clip_detection=True),
    )
    assert result.viral_moments.moments == []
    assert result.viral_moments.provider == "disabled"
    assert Path(result.viral_moments_path).is_file()
    get_settings.cache_clear()
