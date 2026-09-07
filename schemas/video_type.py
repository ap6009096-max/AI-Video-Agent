"""Video type preset schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class VideoTypePreset(BaseModel):
    """One creative format preset from config/video_types.json."""

    id: str = ""
    name: str = ""
    aliases: list[str] = Field(default_factory=list)
    aspect_ratio: str = "9:16"
    pacing: str = "medium"
    caption_style: str = ""
    hook_strategy: str = ""
    visual_requirements: str = ""
    audio_requirements: str = ""
    platform_compatibility: list[str] = Field(default_factory=list)
    default_duration_sec: int = 30
    notes: str = ""


class VideoTypePack(BaseModel):
    """Resolved video type pack for workflow state."""

    source_label: str = ""
    preset: VideoTypePreset = Field(default_factory=VideoTypePreset)
    fallback: bool = False
    notes: str = ""
    created_at: datetime = Field(default_factory=_utc_now)


class VideoTypeResult(BaseModel):
    video_type_pack: VideoTypePack
    video_type_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "video_type_pack": self.video_type_pack.model_dump(mode="json"),
            "messages": list(self.messages),
        }
