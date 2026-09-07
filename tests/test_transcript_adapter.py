"""Tests for Whisper → StructuredTranscript adapter."""

from __future__ import annotations

from schemas.job import SourceType
from schemas.transcript import WhisperSegment, WhisperTranscript, WhisperWord
from tools.whisper.adapter import whisper_to_structured


def test_whisper_to_structured_timings() -> None:
    whisper = WhisperTranscript(
        project_id="p1",
        source_type=SourceType.UPLOAD,
        language="en",
        text="Hello world. Next line.",
        segments=[
            WhisperSegment(
                id=0,
                start=0.0,
                end=1.2,
                text="Hello world.",
                words=[WhisperWord(word="Hello", start=0.0, end=0.4)],
            ),
            WhisperSegment(id=1, start=1.2, end=2.5, text="Next line."),
        ],
        model="base",
    )
    structured = whisper_to_structured(whisper)
    assert structured.provider == "whisper"
    assert structured.language == "en"
    assert len(structured.sentences) == 2
    assert structured.sentences[0].start_seconds == 0.0
    assert structured.sentences[0].end_seconds == 1.2
    assert structured.sentences[1].start_seconds == 1.2
    assert structured.cleaned_text
