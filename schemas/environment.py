"""Environment preset and plan schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EnvironmentPreset(BaseModel):
    """One environment preset from config/environments.json."""

    id: str = ""
    name: str = ""
    aliases: list[str] = Field(default_factory=list)
    visual_description: str = ""
    lighting: str = ""
    color_atmosphere: str = ""
    camera_suggestions: str = ""
    background_requirements: str = ""
    broll_requirements: str = ""
    transition_suggestions: str = ""
    notes: str = ""


class EnvironmentPlan(BaseModel):
    """Structured environment plan for creative/render consumers."""

    environment_name: str = ""
    visual_description: str = ""
    lighting: str = ""
    color_atmosphere: str = ""
    camera_suggestions: str = ""
    background_requirements: str = ""
    broll_requirements: str = ""
    transition_suggestions: str = ""
    summary: str = ""


class EnvironmentPack(BaseModel):
    """Resolved environment pack for workflow state."""

    source_label: str = ""
    preset: EnvironmentPreset = Field(default_factory=EnvironmentPreset)
    plan: EnvironmentPlan = Field(default_factory=EnvironmentPlan)
    fallback: bool = False
    notes: str = ""
    created_at: datetime = Field(default_factory=_utc_now)


class EnvironmentResult(BaseModel):
    environment_pack: EnvironmentPack
    environment_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "environment_pack": self.environment_pack.model_dump(mode="json"),
            "messages": list(self.messages),
        }
