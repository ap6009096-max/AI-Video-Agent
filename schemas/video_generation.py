"""Video generation planning schemas (Prompt 38) — provider-agnostic."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class VideoGenShot(BaseModel):
    """One planned video shot for any downstream generation provider."""

    scene: int = 1
    duration: float = 5.0
    prompt: str = ""
    visual_style: str = ""
    environment: str = ""
    camera_move: str = ""
    shot_type: str = ""
    transition: str = ""
    voiceover: str = ""


class GeminiVideoGenerationBatch(BaseModel):
    """Structured Gemini output for video generation planning."""

    shots: list[VideoGenShot] = Field(default_factory=list)
    notes: str = ""


class VideoGenerationPlan(BaseModel):
    """Canonical plan written to analysis/video_generation_plan.json."""

    shots: list[VideoGenShot] = Field(default_factory=list)
    shot_sequence: list[str] = Field(default_factory=list)
    camera_movement_plan: list[str] = Field(default_factory=list)
    scene_prompts: list[str] = Field(default_factory=list)
    mode: str = ""
    style: str = ""
    environment: str = ""
    provider: str = "none"
    skipped: bool = False
    notes: str = ""


class VideoGenerationPack(BaseModel):
    source_label: str = ""
    plan: VideoGenerationPlan = Field(default_factory=VideoGenerationPlan)
    fallback: bool = False
    notes: str = ""
    created_at: datetime = Field(default_factory=_utc_now)


class VideoGenerationResult(BaseModel):
    video_generation_pack: VideoGenerationPack
    video_generation_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "video_generation_pack": self.video_generation_pack.model_dump(mode="json"),
            "messages": list(self.messages),
        }

    def public_output(self) -> dict[str, Any]:
        """Portable summary for any executor."""
        p = self.video_generation_pack.plan
        return {
            "mode": p.mode,
            "style": p.style,
            "environment": p.environment,
            "shots": [s.model_dump(mode="json") for s in p.shots],
            "shot_sequence": list(p.shot_sequence),
            "camera_movement_plan": list(p.camera_movement_plan),
            "scene_prompts": list(p.scene_prompts),
            "provider": p.provider,
            "skipped": p.skipped,
        }
