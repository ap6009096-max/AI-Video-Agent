"""Director planning schemas (Prompt 39) — continuity & sequencing."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


ContinuityKind = Literal["story", "character", "environment", "camera", "transition"]


class DirectorContinuityNote(BaseModel):
    """Structured continuity bridge between scenes."""

    kind: ContinuityKind = "story"
    from_scene: int = 1
    to_scene: int = 2
    note: str = ""


class DirectorBeat(BaseModel):
    """Optional internal beat detail for a scene in the directed order."""

    scene: int = 1
    summary: str = ""
    camera: str = ""
    environment: str = ""


class GeminiDirectorBatch(BaseModel):
    """Structured Gemini output for director planning."""

    scene_order: list[int] = Field(default_factory=list)
    continuity_notes: list[str] = Field(default_factory=list)
    camera_flow: list[str] = Field(default_factory=list)
    notes: str = ""


class DirectorPlan(BaseModel):
    """Canonical plan written to analysis/director_plan.json."""

    scene_order: list[int] = Field(default_factory=list)
    continuity_notes: list[str] = Field(default_factory=list)
    camera_flow: list[str] = Field(default_factory=list)
    beats: list[DirectorBeat] = Field(default_factory=list)
    structured_notes: list[DirectorContinuityNote] = Field(default_factory=list)
    provider: str = "none"
    skipped: bool = False
    notes: str = ""


class DirectorPack(BaseModel):
    source_label: str = ""
    plan: DirectorPlan = Field(default_factory=DirectorPlan)
    fallback: bool = False
    notes: str = ""
    created_at: datetime = Field(default_factory=_utc_now)


class DirectorResult(BaseModel):
    director_pack: DirectorPack
    director_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "director_pack": self.director_pack.model_dump(mode="json"),
            "messages": list(self.messages),
        }

    def public_output(self) -> dict[str, Any]:
        """Requested public surface."""
        p = self.director_pack.plan
        return {
            "scene_order": list(p.scene_order),
            "continuity_notes": list(p.continuity_notes),
            "camera_flow": list(p.camera_flow),
        }
