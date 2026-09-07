"""Tests for VideoGenerationAgent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.video_generation_agent import VideoGenerationAgent
from config.settings import get_settings
from schemas.job import FeatureFlags, SourceType, VideoJobConfig
from schemas.project import ProjectMetadata
from schemas.video_generation import GeminiVideoGenerationBatch, VideoGenShot
from tools.video_generation.catalog import clear_video_generation_cache


def test_video_generation_flag_off_skips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    clear_video_generation_cache()
    project_dir = tmp_path / "outputs" / "projects" / "vg1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="vg1", source_type=SourceType.SCRIPT, raw_text="x"
    )
    result = VideoGenerationAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(platform="YouTube"),
        features=FeatureFlags(video_generation=False),
    )
    assert result.video_generation_pack.plan.skipped is True
    data = json.loads(Path(result.video_generation_path).read_text(encoding="utf-8"))
    assert data["plan"]["skipped"] is True
    get_settings.cache_clear()


def test_video_generation_writes_plan_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    clear_video_generation_cache()
    project_dir = tmp_path / "outputs" / "projects" / "vg2"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="vg2", source_type=SourceType.SCRIPT, raw_text="x"
    )

    def _fake(**_: object) -> GeminiVideoGenerationBatch:
        return GeminiVideoGenerationBatch(
            shots=[
                VideoGenShot(
                    scene=1,
                    duration=5,
                    prompt="Host on trail, cinematic mist",
                    visual_style="Cinematic",
                    environment="Forest",
                    camera_move="slow push-in",
                    shot_type="medium",
                    transition="cut",
                    voiceover="Start here",
                )
            ]
        )

    result = VideoGenerationAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(platform="YouTube", video_type="Cinematic"),
        features=FeatureFlags(video_generation=True),
        script_pack={"primary": {"title": "Tips", "hook": "Start here"}},
        analyze_fn=_fake,
    )
    plan = result.video_generation_pack.plan
    assert plan.skipped is False
    assert len(plan.shots) == 1
    assert plan.scene_prompts
    assert plan.camera_movement_plan
    assert plan.shot_sequence
    assert plan.provider == "gemini"
    public = result.public_output()
    assert "scene_prompts" in public
    assert "camera_movement_plan" in public
    assert public["provider"] not in {"runway", "pika", "luma", "veo"}
    get_settings.cache_clear()
