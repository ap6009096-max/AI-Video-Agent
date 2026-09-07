"""Structured transcript schemas shared by script and future Whisper paths."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from schemas.job import SourceType


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TextSpan(BaseModel):
    """A text span with character offsets (optional media timestamps)."""

    id: str
    text: str
    start_char: int
    end_char: int
    start_seconds: float | None = None
    end_seconds: float | None = None


class ScriptSentence(TextSpan):
    """A detected sentence within cleaned text."""

    index: int = 0


class ScriptParagraph(TextSpan):
    """A detected paragraph within cleaned text."""

    index: int = 0
    sentence_ids: list[str] = Field(default_factory=list)


class ScriptSection(BaseModel):
    """A logical section (not an arbitrary character chunk)."""

    id: str
    title: str = ""
    summary: str = ""
    start_char: int = 0
    end_char: int = 0
    sentence_ids: list[str] = Field(default_factory=list)


class HookCandidate(BaseModel):
    """A potential opening hook or attention moment."""

    text: str
    sentence_id: str = ""
    reason: str = ""
    score: float = Field(default=0.0, ge=0.0, le=1.0)


class ImportantStatement(BaseModel):
    """A high-value claim or statement worth keeping."""

    text: str
    sentence_id: str = ""
    reason: str = ""


class ClipBoundary(BaseModel):
    """A suggested cut point after a sentence."""

    after_sentence_id: str
    reason: str = ""
    suggested_title: str = ""


class GeminiHook(BaseModel):
    sentence_index: int
    reason: str = ""
    score: float = Field(default=0.5, ge=0.0, le=1.0)


class GeminiImportantStatement(BaseModel):
    sentence_index: int
    reason: str = ""


class GeminiClipBoundary(BaseModel):
    after_sentence_index: int
    reason: str = ""
    suggested_title: str = ""


class GeminiScriptAnalysis(BaseModel):
    """Lean structured output expected from Gemini."""

    language: str = "en"
    topics: list[str] = Field(default_factory=list)
    section_titles: list[str] = Field(default_factory=list)
    hooks: list[GeminiHook] = Field(default_factory=list)
    important_statements: list[GeminiImportantStatement] = Field(default_factory=list)
    clip_boundaries: list[GeminiClipBoundary] = Field(default_factory=list)


class StructuredTranscript(BaseModel):
    """Full transcript.json payload for script and video pipelines."""

    project_id: str
    source_type: SourceType = SourceType.SCRIPT
    language: str = ""
    topics: list[str] = Field(default_factory=list)
    cleaned_text: str = ""
    sentences: list[ScriptSentence] = Field(default_factory=list)
    paragraphs: list[ScriptParagraph] = Field(default_factory=list)
    sections: list[ScriptSection] = Field(default_factory=list)
    hooks: list[HookCandidate] = Field(default_factory=list)
    important_statements: list[ImportantStatement] = Field(default_factory=list)
    clip_boundaries: list[ClipBoundary] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utc_now)
    provider: str = "gemini"


class TextAgentResult(BaseModel):
    """LangGraph-friendly return from the Text Agent."""

    transcript: StructuredTranscript
    transcript_path: str
    source_dir: str = ""
    source_metadata: dict[str, Any] = Field(default_factory=dict)
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "transcript": self.transcript.model_dump(mode="json"),
            "source_dir": self.source_dir,
            "source_metadata": self.source_metadata,
            "messages": list(self.messages),
        }


class WhisperWord(BaseModel):
    """Word-level timing from local Whisper."""

    word: str
    start: float
    end: float
    probability: float | None = None


class WhisperSegment(BaseModel):
    """Segment with optional word timings and confidence."""

    id: int
    start: float
    end: float
    text: str
    words: list[WhisperWord] = Field(default_factory=list)
    avg_logprob: float | None = None
    confidence: float | None = None


class WhisperTranscript(BaseModel):
    """Canonical speech transcript stored under transcripts/transcript.json."""

    project_id: str
    source_type: SourceType
    media_path: str = ""
    language: str = ""
    segments: list[WhisperSegment] = Field(default_factory=list)
    text: str = ""
    provider: str = "whisper-local"
    model: str = "base"
    created_at: datetime = Field(default_factory=_utc_now)


class TranscriptAgentResult(BaseModel):
    """LangGraph-friendly return from the Transcript Agent."""

    speech_transcript: WhisperTranscript
    structured_transcript: StructuredTranscript
    transcript_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "speech_transcript": self.speech_transcript.model_dump(mode="json"),
            "transcript": self.structured_transcript.model_dump(mode="json"),
            "messages": list(self.messages),
        }
