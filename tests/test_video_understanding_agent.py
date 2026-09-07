"""Tests for VideoUnderstandingAgent with mocked OpenCV/FFmpeg tools."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.video_understanding_agent import VideoUnderstandingAgent
from config.settings import get_settings
from schemas.analysis import (
    AudioCharacteristics,
    SampledFrameInfo,
    SceneSegment,
    VideoProperties,
    VisualChange,
)
from schemas.base import JobStatus
from schemas.job import SourceType
from schemas.project import ProjectMetadata


def _fake_probe(_path):
    return VideoProperties(
        duration_seconds=10.0,
        fps=30.0,
        width=1280,
        height=720,
        frame_count=300,
        video_codec="h264",
        audio_codec="aac",
    )


def _fake_scenes(_path, **_kwargs):
    return {
        "sampled_frames": [
            SampledFrameInfo(frame_index=0, time_seconds=0.0, motion_score=0.0),
            SampledFrameInfo(frame_index=30, time_seconds=1.0, motion_score=0.5),
        ],
        "scenes": [
            SceneSegment(id=0, start=0.0, end=1.0, score=0.0),
            SceneSegment(id=1, start=1.0, end=10.0, score=0.5),
        ],
        "visual_changes": [VisualChange(time_seconds=1.0, score=0.5, kind="cut")],
        "object_cues": [],
        "frames_analyzed": 2,
        "effective_sample_fps": 1.0,
    }


def _fake_audio(_path):
    return AudioCharacteristics(
        has_audio=True,
        sample_rate=48000,
        channels=2,
        mean_volume_db=-20.0,
    )


def test_video_understanding_writes_analysis_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()

    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake")
    project_dir = tmp_path / "outputs" / "projects" / "ana-1"
    project_dir.mkdir(parents=True)

    agent = VideoUnderstandingAgent(
        probe_fn=_fake_probe,
        scenes_fn=_fake_scenes,
        audio_fn=_fake_audio,
    )
    project = ProjectMetadata(
        project_id="ana-1",
        source_type=SourceType.UPLOAD,
        source_path=str(video),
        status=JobStatus.RUNNING,
    )
    speech = {
        "segments": [{"start": 0.0, "end": 2.0, "text": "hi"}],
        "language": "en",
    }
    result = agent.run(
        project,
        project_dir=project_dir,
        speech_transcript=speech,
    )

    path = Path(result.analysis_path)
    assert path.is_file()
    assert path.parent.name == "analysis"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["properties"]["duration_seconds"] == 10.0
    assert data["properties"]["fps"] == 30.0
    assert data["properties"]["width"] == 1280
    assert data["scenes"]
    assert data["audio"]["has_audio"] is True
    assert data["speaker_presence"]["speech_ranges"]
    assert data["frames_analyzed"] == 2

    get_settings.cache_clear()


def test_transcript_only_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()

    project_dir = tmp_path / "outputs" / "projects" / "script-ana"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="script-ana",
        source_type=SourceType.SCRIPT,
        raw_text="Hello world.",
    )
    result = VideoUnderstandingAgent().run(
        project,
        project_dir=project_dir,
        transcript={
            "sentences": [
                {"start_seconds": 0.0, "end_seconds": 1.5, "text": "Hello world."}
            ]
        },
    )
    assert result.analysis.provider == "transcript-only"
    assert result.analysis.frames_analyzed == 0
    assert "no local video" in result.analysis.notes.lower()
    assert Path(result.analysis_path).is_file()
    get_settings.cache_clear()
