"""Tests for Whisper transcript schemas."""

from __future__ import annotations

from schemas.job import SourceType
from schemas.transcript import WhisperSegment, WhisperTranscript, WhisperWord


def test_whisper_segment_with_words() -> None:
    seg = WhisperSegment(
        id=0,
        start=0.0,
        end=1.5,
        text="Hello world",
        words=[
            WhisperWord(word="Hello", start=0.0, end=0.5, probability=0.9),
            WhisperWord(word="world", start=0.5, end=1.5, probability=0.8),
        ],
        confidence=0.85,
    )
    assert seg.words[0].word == "Hello"
    assert seg.confidence == 0.85


def test_whisper_transcript_payload() -> None:
    doc = WhisperTranscript(
        project_id="p1",
        source_type=SourceType.UPLOAD,
        media_path="/tmp/a.mp4",
        language="en",
        segments=[
            WhisperSegment(id=0, start=0.0, end=1.0, text="Hi"),
        ],
        text="Hi",
        model="base",
    )
    data = doc.model_dump(mode="json")
    assert data["language"] == "en"
    assert data["segments"][0]["start"] == 0.0
    assert data["segments"][0]["end"] == 1.0
    assert data["segments"][0]["text"] == "Hi"
    assert data["provider"] == "whisper-local"
