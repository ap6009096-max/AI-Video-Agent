"""Motion graphics schemas (Prompt 42) — graphic-layer overlay plan."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


MotionOverlayKind = Literal[
    "kinetic_typography",
    "animated_title",
    "lower_third",
    "data_visualization",
    "chart",
    "statistic",
    "educational_overlay",
]


class MotionOverlay(BaseModel):
    """One graphic overlay instruction."""

    scene: int = 1
    kind: MotionOverlayKind = "animated_title"
    text: str = ""
    style: str = ""
    animation: str = ""
    timing: str = ""
    position: str = ""
    data: str = ""
    notes: str = ""


class GeminiMotionGraphicsBatch(BaseModel):
    """Structured Gemini output for motion graphics planning."""

    overlays: list[MotionOverlay] = Field(default_factory=list)
    notes: str = ""


class MotionGraphicsPlan(BaseModel):
    """Canonical plan written to analysis/motion_graphics_plan.json."""

    overlays: list[MotionOverlay] = Field(default_factory=list)
    motion_plan: list[str] = Field(default_factory=list)
    provider: str = "none"
    skipped: bool = False
    notes: str = ""


class MotionGraphicsPack(BaseModel):
    source_label: str = ""
    plan: MotionGraphicsPlan = Field(default_factory=MotionGraphicsPlan)
    fallback: bool = False
    notes: str = ""
    created_at: datetime = Field(default_factory=_utc_now)


class MotionGraphicsResult(BaseModel):
    motion_graphics_pack: MotionGraphicsPack
    motion_graphics_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "motion_graphics_pack": self.motion_graphics_pack.model_dump(mode="json"),
            "messages": list(self.messages),
        }

    def public_output(self) -> dict[str, Any]:
        """Requested public surface."""
        return {
            "overlays": [
                {
                    "scene": o.scene,
                    "kind": o.kind,
                    "text": o.text,
                    "style": o.style,
                    "animation": o.animation,
                    "timing": o.timing,
                    "position": o.position,
                }
                for o in self.motion_graphics_pack.plan.overlays
            ]
        }
