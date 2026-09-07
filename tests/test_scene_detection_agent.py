"""Tests for SceneDetectionAgent writing analysis/scenes.json."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.scene_detection_agent import SceneDetectionAgent
from config.settings import get_settings
from schemas.base import JobStatus
from schemas.job import SourceType
from schemas.project import ProjectMetadata
from schemas.scenes import DetectedScene


def test_scene_detection_writes_scenes_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()

    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake")
    project_dir = tmp_path / "outputs" / "projects" / "sc-1"
    project_dir.mkdir(parents=True)

    def _fake_detect(**_kwargs):
        return {
            "scenes": [
                DetectedScene(
                    id=0,
                    start=0.0,
                    end=4.0,
                    duration=4.0,
                    visual_change_score=0.0,
                    description="Stable visual segment",
                    change_kinds=[],
                ),
                DetectedScene(
                    id=1,
                    start=4.0,
                    end=10.0,
                    duration=6.0,
                    visual_change_score=0.72,
                    description="Hard cut (score=0.72)",
                    change_kinds=["cut"],
                ),
            ],
            "duration": 10.0,
            "source_signals": {"visual": 1, "speaker": 0, "event": 0, "rescanned": 0},
            "notes": "",
        }

    agent = SceneDetectionAgent(detect_fn=_fake_detect)
    project = ProjectMetadata(
        project_id="sc-1",
        source_type=SourceType.UPLOAD,
        source_path=str(video),
        status=JobStatus.RUNNING,
    )
    result = agent.run(
        project,
        project_dir=project_dir,
        analysis={"properties": {"duration_seconds": 10.0}},
    )

    path = Path(result.scenes_path)
    assert path.is_file()
    assert path.name == "scenes.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data["scenes"]) == 2
    scene = data["scenes"][1]
    assert scene["start"] == 4.0
    assert scene["end"] == 10.0
    assert scene["duration"] == 6.0
    assert scene["visual_change_score"] == 0.72
    assert scene["description"]

    get_settings.cache_clear()


def test_transcript_only_scene_detection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()

    project_dir = tmp_path / "outputs" / "projects" / "script-sc"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="script-sc",
        source_type=SourceType.SCRIPT,
        raw_text="Hello world.",
    )
    result = SceneDetectionAgent().run(
        project,
        project_dir=project_dir,
        analysis={
            "properties": {"duration_seconds": 0.0},
            "provider": "transcript-only",
        },
        transcript={
            "sentences": [
                {"start_seconds": 0.0, "end_seconds": 1.0, "text": "Hello"},
                {"start_seconds": 3.0, "end_seconds": 4.5, "text": "world"},
            ]
        },
    )
    assert result.scenes.provider == "transcript-only"
    assert "no local video" in result.scenes.notes.lower()
    assert Path(result.scenes_path).is_file()
    assert result.scenes.scenes
    get_settings.cache_clear()
