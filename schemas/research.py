"""Research report schemas — sourced topic analysis / claims / outline."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

ResearchSourceKind = Literal[
    "user_script", "transcript", "section", "metadata", "analysis"
]
ResearchClaimType = Literal[
    "fact", "statistic", "definition", "opinion", "other"
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ResearchSource(BaseModel):
    id: str
    kind: ResearchSourceKind | str = "transcript"
    title: str = ""
    locator: str = ""
    excerpt: str = ""
    url: str = ""
    notes: str = ""


class ResearchClaim(BaseModel):
    id: str
    text: str
    claim_type: ResearchClaimType | str = "fact"
    confidence: float = 0.0
    source_ids: list[str] = Field(default_factory=list)
    evidence_excerpts: list[str] = Field(default_factory=list)


class ResearchOutlineSection(BaseModel):
    id: str
    title: str = ""
    summary: str = ""
    bullet_points: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)


class TopicAnalysis(BaseModel):
    primary_topic: str = ""
    subtopics: list[str] = Field(default_factory=list)
    audience: str = ""
    angle: str = ""
    keywords: list[str] = Field(default_factory=list)


class GeminiOutlineSection(BaseModel):
    """Lean Gemini outline section — must reference existing claim ids only."""

    id: str = ""
    title: str = ""
    summary: str = ""
    bullet_points: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)


class GeminiResearchEnrichment(BaseModel):
    """Optional Gemini enrichment — no new claims/sources."""

    primary_topic: str = ""
    subtopics: list[str] = Field(default_factory=list)
    audience: str = ""
    angle: str = ""
    keywords: list[str] = Field(default_factory=list)
    outline: list[GeminiOutlineSection] = Field(default_factory=list)
    summary: str = ""
    notes: str = ""


class ResearchReport(BaseModel):
    project_id: str
    topic: str = ""
    topic_analysis: TopicAnalysis = Field(default_factory=TopicAnalysis)
    sources: list[ResearchSource] = Field(default_factory=list)
    claims: list[ResearchClaim] = Field(default_factory=list)
    outline: list[ResearchOutlineSection] = Field(default_factory=list)
    summary: str = ""
    provider: str = "research-builder"
    created_at: datetime = Field(default_factory=_utc_now)
    notes: str = ""
    skipped: bool = False
    summary_stats: dict[str, float] = Field(default_factory=dict)


class ResearchResult(BaseModel):
    research_report: ResearchReport
    research_report_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "research_report": self.research_report.model_dump(mode="json"),
            "messages": list(self.messages),
        }
