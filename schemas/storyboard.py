"""Storyboard planning schemas (Prompt 37)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StoryboardShot(BaseModel):
    """One storyboard row — public output surface."""

    scene: int = 1
    duration: float = 5.0
    camera: str = ""
    visual: str = ""
    voiceover: str = ""
    transition: str = ""


class GeminiStoryboardBatch(BaseModel):
    """Structured Gemini output for storyboard planning."""

    shots: list[StoryboardShot] = Field(default_factory=list)
    notes: str = ""


class StoryboardPlan(BaseModel):
    """Canonical storyboard plan written to analysis/storyboard_plan.json."""

    shots: list[StoryboardShot] = Field(default_factory=list)
    shot_list: list[StoryboardShot] = Field(default_factory=list)
    scene_list: list[StoryboardShot] = Field(default_factory=list)
    camera_plan: list[str] = Field(default_factory=list)
    transition_plan: list[str] = Field(default_factory=list)
    provider: str = "none"
    skipped: bool = False
    notes: str = ""


class StoryboardPack(BaseModel):
    source_label: str = ""
    plan: StoryboardPlan = Field(default_factory=StoryboardPlan)
    fallback: bool = False
    notes: str = ""
    created_at: datetime = Field(default_factory=_utc_now)


class StoryboardResult(BaseModel):
    storyboard_pack: StoryboardPack
    storyboard_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "storyboard_pack": self.storyboard_pack.model_dump(mode="json"),
            "messages": list(self.messages),
        }

    def public_output(self) -> list[dict[str, Any]]:
        """Requested public shot list shape."""
        return [
            {
                "scene": s.scene,
                "duration": s.duration,
                "camera": s.camera,
                "visual": s.visual,
                "voiceover": s.voiceover,
                "transition": s.transition,
            }
            for s in self.storyboard_pack.plan.shots
        ]
