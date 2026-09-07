"""Moment / highlight detection schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

MomentCategory = Literal[
    "viral",
    "funny",
    "emotional",
    "educational",
    "surprise",
    "important",
    "reaction",
    "inspirational",
    "cinematic",
    "expert_insights",
    "best_quotes",
]

ALL_MOMENT_CATEGORIES: tuple[MomentCategory, ...] = (
    "viral",
    "funny",
    "emotional",
    "educational",
    "surprise",
    "important",
    "reaction",
    "inspirational",
    "cinematic",
    "expert_insights",
    "best_quotes",
)

# FeatureFlags field → MomentCategory
CATEGORY_FLAG_MAP: dict[str, MomentCategory] = {
    "viral_moments": "viral",
    "funny_moments": "funny",
    "emotional_moments": "emotional",
    "educational_moments": "educational",
    "surprise_moments": "surprise",
    "important_moments": "important",
    "reaction_moments": "reaction",
    "inspirational_moments": "inspirational",
    "cinematic_moments": "cinematic",
    "expert_insights": "expert_insights",
    "best_quotes": "best_quotes",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DetectedMoment(BaseModel):
    id: int = 0
    category: MomentCategory
    start: float
    end: float
    title: str = ""
    reason: str = ""
    score: float = 0.0
    transcript: str = ""
    evidence: list[str] = Field(default_factory=list)


class MomentsReport(BaseModel):
    project_id: str
    enabled_categories: list[MomentCategory] = Field(default_factory=list)
    moments: list[DetectedMoment] = Field(default_factory=list)
    provider: str = "multi-signal-heuristics"
    created_at: datetime = Field(default_factory=_utc_now)
    notes: str = ""
    summary_counts: dict[str, int] = Field(default_factory=dict)


class MomentDetectionResult(BaseModel):
    moments: MomentsReport
    moments_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "moments": self.moments.model_dump(mode="json"),
            "messages": list(self.messages),
        }
