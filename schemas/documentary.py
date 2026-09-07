"""Documentary planning schemas (Prompt 43) — narrative arc plan."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DocumentaryChapter(BaseModel):
    """One documentary chapter with optional planning fields."""

    title: str = ""
    summary: str = ""
    research: str = ""
    evidence: str = ""
    narration: str = ""
    interview: str = ""
    timeline: str = ""
    scene: int = 1


class GeminiDocumentaryBatch(BaseModel):
    """Structured Gemini output for documentary planning."""

    introduction: str = ""
    chapters: list[DocumentaryChapter] = Field(default_factory=list)
    conclusion: str = ""
    research_structure: list[str] = Field(default_factory=list)
    evidence_structure: list[str] = Field(default_factory=list)
    narration_plan: list[str] = Field(default_factory=list)
    interview_plan: list[str] = Field(default_factory=list)
    timeline_plan: list[str] = Field(default_factory=list)
    notes: str = ""


class DocumentaryPlan(BaseModel):
    """Canonical plan written to analysis/documentary_plan.json."""

    introduction: str = ""
    chapters: list[DocumentaryChapter] = Field(default_factory=list)
    conclusion: str = ""
    research_structure: list[str] = Field(default_factory=list)
    evidence_structure: list[str] = Field(default_factory=list)
    narration_plan: list[str] = Field(default_factory=list)
    interview_plan: list[str] = Field(default_factory=list)
    timeline_plan: list[str] = Field(default_factory=list)
    documentary_plan: list[str] = Field(default_factory=list)
    provider: str = "none"
    skipped: bool = False
    notes: str = ""


class DocumentaryPack(BaseModel):
    source_label: str = ""
    plan: DocumentaryPlan = Field(default_factory=DocumentaryPlan)
    fallback: bool = False
    notes: str = ""
    created_at: datetime = Field(default_factory=_utc_now)


class DocumentaryResult(BaseModel):
    documentary_pack: DocumentaryPack
    documentary_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "documentary_pack": self.documentary_pack.model_dump(mode="json"),
            "messages": list(self.messages),
        }

    def public_output(self) -> dict[str, Any]:
        """Requested public surface."""
        p = self.documentary_pack.plan
        return {
            "introduction": p.introduction,
            "chapters": [
                {"title": c.title, "summary": c.summary} for c in p.chapters
            ],
            "conclusion": p.conclusion,
        }
