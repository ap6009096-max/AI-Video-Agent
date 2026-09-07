"""Tests for CameraAgent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.camera_agent import CameraAgent
from config.settings import get_settings
from schemas.camera import CameraInstruction, GeminiCameraBatch
from schemas.job import FeatureFlags, SourceType, VideoJobConfig
from schemas.project import ProjectMetadata
from tools.camera.catalog import clear_camera_cache


def test_camera_flag_off_skips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    clear_camera_cache()
    project_dir = tmp_path / "outputs" / "projects" / "cam1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="cam1", source_type=SourceType.SCRIPT, raw_text="x"
    )
    result = CameraAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(platform="YouTube"),
        features=FeatureFlags(camera=False),
    )
    assert result.camera_pack.plan.skipped is True
    path = Path(result.camera_path)
    assert path.name == "camera_plan.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["plan"]["skipped"] is True
    get_settings.cache_clear()


def test_camera_writes_public_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    clear_camera_cache()
    project_dir = tmp_path / "outputs" / "projects" / "cam2"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="cam2", source_type=SourceType.SCRIPT, raw_text="x"
    )

    def _fake(**_: object) -> GeminiCameraBatch:
        return GeminiCameraBatch(
            instructions=[
                CameraInstruction(
                    scene=1,
                    shot_type="wide",
                    movement="locked-off hold",
                    instruction="Wide establish on the trail.",
                ),
                CameraInstruction(
                    scene=2,
                    shot_type="tracking",
                    movement="lateral follow",
                    instruction="Track the host along the path.",
                ),
            ]
        )

    result = CameraAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(platform="YouTube"),
        features=FeatureFlags(camera=True),
        script_pack={"primary": {"title": "Tips", "hook": "Start here"}},
        analyze_fn=_fake,
    )
    public = result.public_output()
    assert "instructions" in public
    assert len(public["instructions"]) == 2
    assert set(public["instructions"][0].keys()) == {
        "scene",
        "shot_type",
        "movement",
        "instruction",
    }
    assert Path(result.camera_path).name == "camera_plan.json"
    get_settings.cache_clear()
