"""Tests for MotionGraphicsAgent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.motion_graphics_agent import MotionGraphicsAgent
from config.settings import get_settings
from schemas.job import FeatureFlags, SourceType, VideoJobConfig
from schemas.motion_graphics import GeminiMotionGraphicsBatch, MotionOverlay
from schemas.project import ProjectMetadata
from tools.motion_graphics.catalog import clear_motion_graphics_cache


def test_motion_graphics_flag_off_skips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    clear_motion_graphics_cache()
    project_dir = tmp_path / "outputs" / "projects" / "mg1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="mg1", source_type=SourceType.SCRIPT, raw_text="x"
    )
    result = MotionGraphicsAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(platform="YouTube"),
        features=FeatureFlags(motion_graphics=False),
    )
    assert result.motion_graphics_pack.plan.skipped is True
    path = Path(result.motion_graphics_path)
    assert path.name == "motion_graphics_plan.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["plan"]["skipped"] is True
    get_settings.cache_clear()


def test_motion_graphics_writes_public_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    clear_motion_graphics_cache()
    project_dir = tmp_path / "outputs" / "projects" / "mg2"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="mg2", source_type=SourceType.SCRIPT, raw_text="x"
    )

    def _fake(**_: object) -> GeminiMotionGraphicsBatch:
        return GeminiMotionGraphicsBatch(
            overlays=[
                MotionOverlay(
                    scene=1,
                    kind="animated_title",
                    text="Hello",
                    style="clean",
                    animation="fade-up",
                    timing="0-3s",
                    position="center",
                ),
                MotionOverlay(
                    scene=2,
                    kind="lower_third",
                    text="Alex",
                    style="bar",
                    animation="slide-in",
                    timing="1-4s",
                    position="lower left",
                ),
            ]
        )

    result = MotionGraphicsAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(platform="YouTube"),
        features=FeatureFlags(motion_graphics=True),
        script_pack={"primary": {"title": "Tips", "hook": "Start here"}},
        analyze_fn=_fake,
    )
    public = result.public_output()
    assert "overlays" in public
    assert len(public["overlays"]) == 2
    assert set(public["overlays"][0].keys()) == {
        "scene",
        "kind",
        "text",
        "style",
        "animation",
        "timing",
        "position",
    }
    assert Path(result.motion_graphics_path).name == "motion_graphics_plan.json"
    get_settings.cache_clear()
