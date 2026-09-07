"""Visual style preset and plan schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class VisualStylePreset(BaseModel):
    """One visual style preset from config/visual_styles.json."""

    id: str = ""
    name: str = ""
    aliases: list[str] = Field(default_factory=list)
    medium: str = ""
    line_quality: str = ""
    shading: str = ""
    color_palette: str = ""
    lighting: str = ""
    texture: str = ""
    camera_motion: str = ""
    composition: str = ""
    motion_feel: str = ""
    render_notes: str = ""
    avoid: str = (
        "Do not imitate a living artist or copyrighted studio look; describe traits only."
    )
    notes: str = ""


class VisualStylePlan(BaseModel):
    """Structured visual plan for creative/render consumers."""

    style_name: str = ""
    medium: str = ""
    line_quality: str = ""
    shading: str = ""
    color_palette: str = ""
    lighting: str = ""
    texture: str = ""
    camera_motion: str = ""
    composition: str = ""
    motion_feel: str = ""
    render_notes: str = ""
    avoid: str = ""
    summary: str = ""


class VisualStylePack(BaseModel):
    """Resolved visual style pack for workflow state."""

    source_label: str = ""
    preset: VisualStylePreset = Field(default_factory=VisualStylePreset)
    plan: VisualStylePlan = Field(default_factory=VisualStylePlan)
    sanitized: bool = False
    fallback: bool = False
    notes: str = ""
    created_at: datetime = Field(default_factory=_utc_now)


class VisualStyleResult(BaseModel):
    visual_style_pack: VisualStylePack
    visual_style_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "visual_style_pack": self.visual_style_pack.model_dump(mode="json"),
            "messages": list(self.messages),
        }
