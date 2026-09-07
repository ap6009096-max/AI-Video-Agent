"""Smart clip selection schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

ClipCategory = Literal[
    "viral",
    "funny",
    "important",
    "emotional",
    "educational",
    "surprise",
    "reaction",
    "inspirational",
    "cinematic",
    "expert",
    "quote",
    "mixed",
    "story",
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ClipCandidate(BaseModel):
    id: int = 0
    start: float
    end: float
    duration: float = 0.0
    transcript: str = ""
    category: ClipCategory | str = "story"
    score: float = 0.0
    hook: str = ""
    reason: str = ""
    title: str = ""
    evidence: list[str] = Field(default_factory=list)
    target_duration: float = 0.0
    source_signals: list[str] = Field(default_factory=list)


class ClipsReport(BaseModel):
    project_id: str
    clips: list[ClipCandidate] = Field(default_factory=list)
    target_duration: float = 30.0
    short_durations: list[int] = Field(default_factory=list)
    multi_shorts: bool = False
    provider: str = "smart-clip-boundaries"
    created_at: datetime = Field(default_factory=_utc_now)
    notes: str = ""
    summary: dict[str, float] = Field(default_factory=dict)


class SmartClipResult(BaseModel):
    clips: ClipsReport
    clips_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "clips": self.clips.model_dump(mode="json"),
            "messages": list(self.messages),
        }
