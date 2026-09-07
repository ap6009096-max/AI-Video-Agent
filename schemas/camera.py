"""Camera planning schemas (Prompt 41) — per-scene camera instructions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


CameraShotType = Literal[
    "wide",
    "medium",
    "close_up",
    "extreme_close_up",
    "drone",
    "tracking",
    "pov",
    "cinematic",
]


class CameraInstruction(BaseModel):
    """One per-scene camera instruction."""

    scene: int = 1
    shot_type: CameraShotType = "medium"
    movement: str = ""
    instruction: str = ""
    lens: str = ""
    notes: str = ""


class GeminiCameraBatch(BaseModel):
    """Structured Gemini output for camera planning."""

    instructions: list[CameraInstruction] = Field(default_factory=list)
    notes: str = ""


class CameraPlan(BaseModel):
    """Canonical plan written to analysis/camera_plan.json."""

    instructions: list[CameraInstruction] = Field(default_factory=list)
    camera_plan: list[str] = Field(default_factory=list)
    provider: str = "none"
    skipped: bool = False
    notes: str = ""


class CameraPack(BaseModel):
    source_label: str = ""
    plan: CameraPlan = Field(default_factory=CameraPlan)
    fallback: bool = False
    notes: str = ""
    created_at: datetime = Field(default_factory=_utc_now)


class CameraResult(BaseModel):
    camera_pack: CameraPack
    camera_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "camera_pack": self.camera_pack.model_dump(mode="json"),
            "messages": list(self.messages),
        }

    def public_output(self) -> dict[str, Any]:
        """Requested public surface."""
        return {
            "instructions": [
                {
                    "scene": i.scene,
                    "shot_type": i.shot_type,
                    "movement": i.movement,
                    "instruction": i.instruction,
                }
                for i in self.camera_pack.plan.instructions
            ]
        }
