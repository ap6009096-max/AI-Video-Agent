"""Image generation schemas (Prompt 36)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


ImageKind = Literal["scene", "storyboard", "broll", "thumbnail", "background"]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GeminiImageItem(BaseModel):
    """One image prompt from Gemini (paths filled after write)."""

    scene_id: str = ""
    prompt: str = ""
    style: str = ""
    environment: str = ""
    kind: ImageKind = "scene"


class GeminiImageBatch(BaseModel):
    """Structured Gemini output for image planning."""

    items: list[GeminiImageItem] = Field(default_factory=list)
    notes: str = ""


class ImageAssetItem(BaseModel):
    """Public image asset surface + kind."""

    scene_id: str = ""
    prompt: str = ""
    style: str = ""
    environment: str = ""
    image_path: str = ""
    kind: ImageKind = "scene"


class ImagePlan(BaseModel):
    """Canonical image plan written to analysis/image_plan.json."""

    items: list[ImageAssetItem] = Field(default_factory=list)
    style: str = ""
    environment: str = ""
    provider: str = "none"
    skipped: bool = False
    notes: str = ""


class ImagePack(BaseModel):
    source_label: str = ""
    plan: ImagePlan = Field(default_factory=ImagePlan)
    fallback: bool = False
    notes: str = ""
    created_at: datetime = Field(default_factory=_utc_now)


class ImageResult(BaseModel):
    image_pack: ImagePack
    image_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "image_pack": self.image_pack.model_dump(mode="json"),
            "messages": list(self.messages),
        }

    def public_output(self) -> list[dict[str, Any]]:
        """Requested public item shapes (without kind)."""
        out: list[dict[str, Any]] = []
        for item in self.image_pack.plan.items:
            out.append(
                {
                    "scene_id": item.scene_id,
                    "prompt": item.prompt,
                    "style": item.style,
                    "environment": item.environment,
                    "image_path": item.image_path,
                }
            )
        return out
