"""Analytics prediction schemas (Prompt 34)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


PREDICTION_DISCLAIMER = "This is a prediction model, not a guarantee."


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GeminiAnalyticsAnalysis(BaseModel):
    """Structured Gemini output for performance prediction."""

    engagement_score: float = 0.0
    retention_score: float = 0.0
    shareability_score: float = 0.0
    watch_time_score: float = 0.0
    ctr_score: float = 0.0
    engagement_drivers: list[str] = Field(default_factory=list)
    retention_drivers: list[str] = Field(default_factory=list)
    shareability_drivers: list[str] = Field(default_factory=list)
    rationale: str = ""


class AnalyticsPlan(BaseModel):
    """Canonical analytics plan — includes requested public output surface."""

    engagement_score: float = 0.0
    retention_score: float = 0.0
    shareability_score: float = 0.0
    watch_time_score: float = 0.0
    ctr_score: float = 0.0
    engagement_drivers: list[str] = Field(default_factory=list)
    retention_drivers: list[str] = Field(default_factory=list)
    shareability_drivers: list[str] = Field(default_factory=list)
    rationale: str = ""
    platform: str = ""
    provider: str = "none"
    skipped: bool = False
    notes: str = ""


class AnalyticsPack(BaseModel):
    source_label: str = ""
    plan: AnalyticsPlan = Field(default_factory=AnalyticsPlan)
    fallback: bool = False
    notes: str = ""
    created_at: datetime = Field(default_factory=_utc_now)


class AnalyticsResult(BaseModel):
    analytics_pack: AnalyticsPack
    analytics_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "analytics_pack": self.analytics_pack.model_dump(mode="json"),
            "messages": list(self.messages),
        }

    def public_output(self) -> dict[str, Any]:
        """Minimal requested output shape."""
        p = self.analytics_pack.plan
        return {
            "engagement_score": p.engagement_score,
            "retention_score": p.retention_score,
            "shareability_score": p.shareability_score,
        }
