"""Smart reframing plan and result schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


FocusKind = Literal[
    "face", "speaker_face", "object", "motion", "fallback_center"
]


class AspectPreset(BaseModel):
    id: str = ""
    name: str = ""
    aliases: list[str] = Field(default_factory=list)
    ratio: float = 0.5625
    output_width: int = 1080
    output_height: int = 1920
    notes: str = ""


class FocusRoi(BaseModel):
    kind: FocusKind | str = "face"
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0
    score: float = 0.0
    time_seconds: float = 0.0


class CropWindow(BaseModel):
    start: float = 0.0
    end: float = 0.0
    crop_x: int = 0
    crop_y: int = 0
    crop_w: int = 0
    crop_h: int = 0
    focus_x: float = 0.0
    focus_y: float = 0.0
    method: str = "face"
    notes: str = ""


class ReframeClipPlan(BaseModel):
    clip_id: int = 0
    src_start: float = 0.0
    src_end: float = 0.0
    windows: list[CropWindow] = Field(default_factory=list)


class ReframePlan(BaseModel):
    project_id: str = ""
    source_width: int = 0
    source_height: int = 0
    source_aspect: float = 0.0
    target_aspect: str = "9:16"
    target_ratio: float = 0.5625
    output_width: int = 1080
    output_height: int = 1920
    passthrough: bool = False
    skipped: bool = False
    encoded: bool = False
    output_path: str = ""
    clip_plans: list[ReframeClipPlan] = Field(default_factory=list)
    focus_samples: list[FocusRoi] = Field(default_factory=list)
    notes: str = ""
    created_at: datetime = Field(default_factory=_utc_now)


class ReframePack(BaseModel):
    plan: ReframePlan = Field(default_factory=ReframePlan)
    aspect: AspectPreset = Field(default_factory=AspectPreset)
    notes: str = ""
    created_at: datetime = Field(default_factory=_utc_now)


class ReframeResult(BaseModel):
    reframe_pack: ReframePack
    reframe_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "reframe_pack": self.reframe_pack.model_dump(mode="json"),
            "messages": list(self.messages),
        }
