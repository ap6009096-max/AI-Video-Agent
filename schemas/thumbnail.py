"""Thumbnail planning schemas (Prompt 30)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ThumbnailPreset(BaseModel):
    id: str = ""
    name: str = ""
    aliases: list[str] = Field(default_factory=list)
    layout: str = ""
    face_zone: str = "center"
    aspect_hint: str = "16:9"
    default_emotion: str = "curious"
    notes: str = ""


class ThumbnailPlan(BaseModel):
    """Canonical thumbnail plan — includes requested public output surface."""

    title: str = ""
    hook: str = ""
    thumbnail_text: str = ""
    emotion: str = ""
    layout: str = ""
    face_placement: str = ""
    click_titles: list[str] = Field(default_factory=list)
    platform: str = ""
    skipped: bool = False
    notes: str = ""


class ThumbnailPack(BaseModel):
    source_label: str = ""
    preset: ThumbnailPreset = Field(default_factory=ThumbnailPreset)
    plan: ThumbnailPlan = Field(default_factory=ThumbnailPlan)
    fallback: bool = False
    notes: str = ""
    created_at: datetime = Field(default_factory=_utc_now)


class ThumbnailResult(BaseModel):
    thumbnail_pack: ThumbnailPack
    thumbnail_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "thumbnail_pack": self.thumbnail_pack.model_dump(mode="json"),
            "messages": list(self.messages),
        }

    def public_output(self) -> dict[str, str]:
        """Minimal requested output shape."""
        p = self.thumbnail_pack.plan
        return {
            "title": p.title,
            "hook": p.hook,
            "thumbnail_text": p.thumbnail_text,
            "emotion": p.emotion,
            "layout": p.layout,
        }
