"""Audio and speaker analysis schemas (evidence for later moment agents)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

EvidenceTag = Literal["funny", "viral", "emotional", "reaction", "clip_boundary"]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ScoredSpan(BaseModel):
    start: float
    end: float
    score: float = 0.0
    label: str = ""
    evidence_tags: list[EvidenceTag] = Field(default_factory=list)
    detail: str = ""


class SpeakerTurn(BaseModel):
    id: int
    start: float
    end: float
    text_excerpt: str = ""
    change_score: float = 0.0


class ConversationalStructure(BaseModel):
    turn_taking: float = 0.0
    overlap_proxy: float = 0.0
    monologue_ratio: float = 0.0
    backchannel_density: float = 0.0


class AudioAnalysisReport(BaseModel):
    project_id: str
    media_path: str = ""
    provider: str = "ffmpeg-transcript"
    created_at: datetime = Field(default_factory=_utc_now)
    notes: str = ""
    silence_spans: list[ScoredSpan] = Field(default_factory=list)
    pause_spans: list[ScoredSpan] = Field(default_factory=list)
    volume_events: list[ScoredSpan] = Field(default_factory=list)
    intensity_spans: list[ScoredSpan] = Field(default_factory=list)
    laughter_candidates: list[ScoredSpan] = Field(default_factory=list)
    excitement_candidates: list[ScoredSpan] = Field(default_factory=list)
    question_spans: list[ScoredSpan] = Field(default_factory=list)
    reaction_spans: list[ScoredSpan] = Field(default_factory=list)
    summary_scores: dict[str, float] = Field(default_factory=dict)


class SpeakerAnalysisReport(BaseModel):
    project_id: str
    media_path: str = ""
    provider: str = "transcript-heuristics"
    created_at: datetime = Field(default_factory=_utc_now)
    notes: str = (
        "Speaker-independent turn heuristics — not true diarization or voice IDs."
    )
    turns: list[SpeakerTurn] = Field(default_factory=list)
    speaker_change_candidates: list[ScoredSpan] = Field(default_factory=list)
    conversational_structure: ConversationalStructure = Field(
        default_factory=ConversationalStructure
    )
    summary_scores: dict[str, float] = Field(default_factory=dict)


class AudioAnalysisResult(BaseModel):
    audio_analysis: AudioAnalysisReport
    audio_analysis_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "audio_analysis": self.audio_analysis.model_dump(mode="json"),
            "messages": list(self.messages),
        }


class SpeakerAnalysisResult(BaseModel):
    speakers: SpeakerAnalysisReport
    speakers_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "speakers": self.speakers.model_dump(mode="json"),
            "messages": list(self.messages),
        }
