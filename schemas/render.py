"""Render planning schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RenderOp(BaseModel):
    name: str = ""
    detail: str = ""


class RenderPlan(BaseModel):
    project_id: str = ""
    source_path: str = ""
    ops: list[RenderOp] = Field(default_factory=list)
    target_width: int = 1080
    target_height: int = 1920
    target_aspect: str = "9:16"
    burn_captions: bool = False
    caption_path: str = ""
    output_path: str = ""
    thumbnail_path: str = ""
    short_paths: list[str] = Field(default_factory=list)
    short_errors: list[str] = Field(default_factory=list)
    encoded: bool = False
    skipped: bool = False
    notes: str = ""
    created_at: datetime = Field(default_factory=_utc_now)


class RenderPack(BaseModel):
    plan: RenderPlan = Field(default_factory=RenderPlan)
    notes: str = ""
    created_at: datetime = Field(default_factory=_utc_now)


class RenderResult(BaseModel):
    render_pack: RenderPack
    render_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "render_pack": self.render_pack.model_dump(mode="json"),
            "messages": list(self.messages),
        }
