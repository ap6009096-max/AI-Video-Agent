"""Tests for StoryboardAgent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.storyboard_agent import StoryboardAgent
from config.settings import get_settings
from schemas.job import FeatureFlags, SourceType, VideoJobConfig
from schemas.project import ProjectMetadata
from schemas.storyboard import GeminiStoryboardBatch, StoryboardShot
from tools.storyboard.catalog import clear_storyboard_cache


def test_storyboard_flag_off_skips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    clear_storyboard_cache()
    project_dir = tmp_path / "outputs" / "projects" / "sb1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="sb1", source_type=SourceType.SCRIPT, raw_text="x"
    )
    result = StoryboardAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(platform="YouTube"),
        features=FeatureFlags(storyboard=False),
    )
    assert result.storyboard_pack.plan.skipped is True
    data = json.loads(Path(result.storyboard_path).read_text(encoding="utf-8"))
    assert data["plan"]["skipped"] is True
    get_settings.cache_clear()


def test_storyboard_writes_public_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    clear_storyboard_cache()
    project_dir = tmp_path / "outputs" / "projects" / "sb2"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="sb2", source_type=SourceType.SCRIPT, raw_text="x"
    )

    def _fake(**_: object) -> GeminiStoryboardBatch:
        return GeminiStoryboardBatch(
            shots=[
                StoryboardShot(
                    scene=1,
                    duration=5,
                    camera="medium shot",
                    visual="Host on trail",
                    voiceover="Start here",
                    transition="cut",
                )
            ]
        )

    result = StoryboardAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(platform="YouTube"),
        features=FeatureFlags(storyboard=True),
        script_pack={"primary": {"title": "Tips", "hook": "Start here"}},
        analyze_fn=_fake,
    )
    plan = result.storyboard_pack.plan
    assert plan.skipped is False
    assert len(plan.shots) == 1
    public = result.public_output()
    assert set(public[0].keys()) == {
        "scene",
        "duration",
        "camera",
        "visual",
        "voiceover",
        "transition",
    }
    assert plan.camera_plan
    assert plan.transition_plan
    get_settings.cache_clear()
