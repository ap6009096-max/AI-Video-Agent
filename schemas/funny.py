"""Funny moment detection schemas (dedicated humor agent)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

HumorKind = Literal[
    "joke",
    "punchline",
    "unexpected_statement",
    "awkward",
    "sarcasm",
    "reaction",
    "laughter",
    "visual_event",
    "comedic_timing",
    "conversational",
    "meme_worthy",
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class FunnyMoment(BaseModel):
    id: int = 0
    start: float
    end: float
    category: Literal["funny"] = "funny"
    humor_kinds: list[HumorKind] = Field(default_factory=list)
    humor_score: float = 0.0
    explanation: str = ""
    transcript: str = ""
    suggested_title: str = ""
    evidence: list[str] = Field(default_factory=list)


class FunnyMomentsReport(BaseModel):
    project_id: str
    moments: list[FunnyMoment] = Field(default_factory=list)
    provider: str = "multi-signal-humor"
    created_at: datetime = Field(default_factory=_utc_now)
    notes: str = ""
    summary: dict[str, float] = Field(default_factory=dict)


class FunnyMomentResult(BaseModel):
    funny_moments: FunnyMomentsReport
    funny_moments_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "funny_moments": self.funny_moments.model_dump(mode="json"),
            "messages": list(self.messages),
        }
