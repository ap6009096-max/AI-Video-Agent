"""Trend detection schemas (Prompt 32)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GeminiTrendAnalysis(BaseModel):
    """Structured Gemini output for trend analysis."""

    trend_score: float = 0.0
    trend_topics: list[str] = Field(default_factory=list)
    recommended_tags: list[str] = Field(default_factory=list)
    trending_hashtags: list[str] = Field(default_factory=list)
    trending_keywords: list[str] = Field(default_factory=list)
    viral_patterns: list[str] = Field(default_factory=list)
    audience_relevance: str = ""
    topic_labels: list[str] = Field(default_factory=list)


class TrendPlan(BaseModel):
    """Canonical trend plan — includes requested public output surface."""

    trend_score: float = 0.0
    trend_topics: list[str] = Field(default_factory=list)
    recommended_tags: list[str] = Field(default_factory=list)
    trending_hashtags: list[str] = Field(default_factory=list)
    trending_keywords: list[str] = Field(default_factory=list)
    viral_patterns: list[str] = Field(default_factory=list)
    audience_relevance: str = ""
    topic_labels: list[str] = Field(default_factory=list)
    platform: str = ""
    provider: str = "none"
    skipped: bool = False
    notes: str = ""


class TrendPack(BaseModel):
    source_label: str = ""
    plan: TrendPlan = Field(default_factory=TrendPlan)
    fallback: bool = False
    notes: str = ""
    created_at: datetime = Field(default_factory=_utc_now)


class TrendResult(BaseModel):
    trend_pack: TrendPack
    trend_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "trend_pack": self.trend_pack.model_dump(mode="json"),
            "messages": list(self.messages),
        }

    def public_output(self) -> dict[str, Any]:
        """Minimal requested output shape."""
        p = self.trend_pack.plan
        return {
            "trend_score": p.trend_score,
            "trend_topics": list(p.trend_topics),
            "recommended_tags": list(p.recommended_tags),
        }
