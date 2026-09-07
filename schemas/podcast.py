"""Podcast clip packaging schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

PodcastClipKind = Literal["quote", "funny", "viral", "lesson", "highlight", "clip"]
PodcastPlatform = Literal["shorts", "reels", "tiktok", "highlights", "quotes", "clips"]
PodcastSourceMedia = Literal["video", "audio", "unknown"]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PodcastClip(BaseModel):
    id: int = 0
    start: float
    end: float
    duration: float = 0.0
    kind: PodcastClipKind | str = "clip"
    platforms: list[PodcastPlatform | str] = Field(default_factory=list)
    transcript: str = ""
    title: str = ""
    hook: str = ""
    reason: str = ""
    score: float = 0.0
    evidence: list[str] = Field(default_factory=list)
    source_category: str = ""


class PodcastClipsReport(BaseModel):
    project_id: str
    clips: list[PodcastClip] = Field(default_factory=list)
    source_media: PodcastSourceMedia = "unknown"
    provider: str = "podcast-packager"
    created_at: datetime = Field(default_factory=_utc_now)
    notes: str = ""
    summary: dict[str, float] = Field(default_factory=dict)


class PodcastResult(BaseModel):
    podcast_clips: PodcastClipsReport
    podcast_clips_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "podcast_clips": self.podcast_clips.model_dump(mode="json"),
            "messages": list(self.messages),
        }
