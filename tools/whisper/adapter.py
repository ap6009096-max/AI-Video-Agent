"""Adapters between Whisper transcripts and shared StructuredTranscript."""

from __future__ import annotations

from schemas.job import SourceType
from schemas.transcript import (
    ScriptSentence,
    StructuredTranscript,
    WhisperTranscript,
)


def whisper_to_structured(whisper: WhisperTranscript) -> StructuredTranscript:
    """Map timed Whisper segments into StructuredTranscript for shared pipeline state."""
    sentences: list[ScriptSentence] = []
    cursor = 0
    parts: list[str] = []
    for idx, seg in enumerate(whisper.segments):
        text = (seg.text or "").strip()
        if not text:
            continue
        if parts:
            cursor += 1  # space joiner
        start_char = cursor
        end_char = start_char + len(text)
        sentences.append(
            ScriptSentence(
                id=f"s{idx}",
                index=idx,
                text=text,
                start_char=start_char,
                end_char=end_char,
                start_seconds=seg.start,
                end_seconds=seg.end,
            )
        )
        parts.append(text)
        cursor = end_char

    cleaned = whisper.text.strip() or " ".join(parts)
    return StructuredTranscript(
        project_id=whisper.project_id,
        source_type=whisper.source_type,
        language=whisper.language or "unknown",
        topics=[],
        cleaned_text=cleaned,
        sentences=sentences,
        paragraphs=[],
        sections=[],
        hooks=[],
        important_statements=[],
        clip_boundaries=[],
        provider="whisper",
    )
