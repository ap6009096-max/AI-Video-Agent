"""Tests for TranscriptAgent with mocked Whisper."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.transcript_agent import TranscriptAgent
from config.settings import get_settings
from core.errors import TranscriptAgentError
from schemas.base import JobStatus
from schemas.job import SourceType
from schemas.project import ProjectMetadata
from schemas.transcript import WhisperSegment, WhisperWord


def _fake_transcribe(media_path):
    return {
        "language": "en",
        "text": "Hello world from video",
        "model": "base",
        "segments": [
            WhisperSegment(
                id=0,
                start=0.0,
                end=1.8,
                text="Hello world from video",
                words=[
                    WhisperWord(word="Hello", start=0.0, end=0.4, probability=0.95),
                    WhisperWord(word="world", start=0.4, end=0.9, probability=0.9),
                ],
                confidence=0.9,
            )
        ],
        "raw": {},
    }


def test_transcript_agent_writes_speech_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()

    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake-video")
    project_dir = tmp_path / "outputs" / "projects" / "vid-1"
    project_dir.mkdir(parents=True)

    # Avoid FFmpeg dependency in unit test
    monkeypatch.setattr(
        "agents.transcript_agent.extract_wav_for_asr",
        lambda *_a, **_k: None,
    )

    project = ProjectMetadata(
        project_id="vid-1",
        source_type=SourceType.UPLOAD,
        source_path=str(video),
        status=JobStatus.RUNNING,
    )
    result = TranscriptAgent(transcribe_fn=_fake_transcribe).run(
        project, project_dir=project_dir
    )

    path = Path(result.transcript_path)
    assert path.is_file()
    assert path.parent.name == "transcripts"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["language"] == "en"
    assert data["segments"][0]["start"] == 0.0
    assert data["segments"][0]["end"] == 1.8
    assert data["segments"][0]["text"]
    assert data["segments"][0]["words"]
    assert data["segments"][0]["confidence"] == 0.9
    assert result.structured_transcript.sentences[0].start_seconds == 0.0

    get_settings.cache_clear()


def test_transcript_agent_requires_local_media(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()

    project = ProjectMetadata(
        project_id="yt-only",
        source_type=SourceType.YOUTUBE,
        youtube_url="https://www.youtube.com/watch?v=abcdefghijk",
        source_path="",
    )
    with pytest.raises(TranscriptAgentError, match="No local media"):
        TranscriptAgent(transcribe_fn=_fake_transcribe).run(
            project, project_dir=tmp_path / "p"
        )
    get_settings.cache_clear()
