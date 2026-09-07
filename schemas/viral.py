"""Viral moment detection schemas (dedicated ranking agent)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ViralScoreBreakdown(BaseModel):
    """Per-dimension scores (0–1) with short reasons."""

    hook: float = 0.0
    information: float = 0.0
    emotion: float = 0.0
    humor: float = 0.0
    visual: float = 0.0
    completeness: float = 0.0
    shareability: float = 0.0
    reasons: dict[str, str] = Field(default_factory=dict)


class ViralMoment(BaseModel):
    id: int = 0
    start: float
    end: float
    category: Literal["viral"] = "viral"
    scores: ViralScoreBreakdown = Field(default_factory=ViralScoreBreakdown)
    final_score: float = 0.0
    rank: int = 0
    explanation: str = ""
    transcript: str = ""
    suggested_title: str = ""
    evidence: list[str] = Field(default_factory=list)


class ViralMomentsReport(BaseModel):
    project_id: str
    moments: list[ViralMoment] = Field(default_factory=list)
    provider: str = "multi-signal-viral-rank"
    created_at: datetime = Field(default_factory=_utc_now)
    notes: str = ""
    summary: dict[str, float] = Field(default_factory=dict)


class ViralMomentResult(BaseModel):
    viral_moments: ViralMomentsReport
    viral_moments_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "viral_moments": self.viral_moments.model_dump(mode="json"),
            "messages": list(self.messages),
        }
