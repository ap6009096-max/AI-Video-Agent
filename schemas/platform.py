"""Platform optimization schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DurationRange(BaseModel):
    min: float = 0.0
    max: float = 60.0
    ideal: float = 30.0


class TitleRequirements(BaseModel):
    max_chars: int = 0
    required: bool = False
    notes: str = ""


class SafeTextArea(BaseModel):
    margin_l: int = 40
    margin_r: int = 40
    margin_v: int = 120


class PlatformPreset(BaseModel):
    id: str = ""
    name: str = ""
    aliases: list[str] = Field(default_factory=list)
    official_url: str = ""
    supported_aspect_ratios: list[str] = Field(default_factory=list)
    recommended_duration_seconds: DurationRange = Field(default_factory=DurationRange)
    caption_behavior: str = ""
    title_requirements: TitleRequirements = Field(default_factory=TitleRequirements)
    cta_strategy: str = ""
    metadata_requirements: list[str] = Field(default_factory=list)
    hook_style: str = ""
    pacing: str = ""
    safe_text_area: SafeTextArea = Field(default_factory=SafeTextArea)
    subreddit_dependent: bool = False
    publish_enabled: bool = False
    notes: str = ""


class PlatformMetadata(BaseModel):
    title: str = ""
    description: str = ""
    caption: str = ""
    hashtags: list[str] = Field(default_factory=list)
    cta: str = ""
    tags: list[str] = Field(default_factory=list)
    aspect_recommendation: str = ""
    duration_recommendation: DurationRange = Field(default_factory=DurationRange)
    hook: str = ""
    thumbnail_text: str = ""
    warnings: list[str] = Field(default_factory=list)


class PlatformExportHints(BaseModel):
    preferred_aspect: str = ""
    caption_burn_in: bool = True
    safe_margins: SafeTextArea = Field(default_factory=SafeTextArea)
    file_naming: str = ""
    publish_status: str = "not_published"
    official_url: str = ""
    publish_enabled: bool = False
    notes: str = (
        "Opening official_url is reference only — not publishing. "
        "Automatic publishing requires official APIs, OAuth, and user authorization later."
    )


class PlatformPlan(BaseModel):
    project_id: str = ""
    platform_name: str = ""
    skipped: bool = False
    metadata: PlatformMetadata = Field(default_factory=PlatformMetadata)
    export_hints: PlatformExportHints = Field(default_factory=PlatformExportHints)
    notes: str = ""
    created_at: datetime = Field(default_factory=_utc_now)


class PlatformPack(BaseModel):
    source_label: str = ""
    preset: PlatformPreset = Field(default_factory=PlatformPreset)
    plan: PlatformPlan = Field(default_factory=PlatformPlan)
    fallback: bool = False
    export_path: str = ""
    notes: str = ""
    created_at: datetime = Field(default_factory=_utc_now)


class PlatformResult(BaseModel):
    platform_pack: PlatformPack
    platform_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "platform_pack": self.platform_pack.model_dump(mode="json"),
            "messages": list(self.messages),
        }
