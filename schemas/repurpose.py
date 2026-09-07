"""Content repurposing schemas (Prompt 33)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

SourceKind = Literal["video", "podcast", "article", "transcript"]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GeminiRepurposeBatch(BaseModel):
    """Structured Gemini output for multi-format repurposing."""

    reels: str = ""
    shorts: str = ""
    tiktok: str = ""
    blog_summary: str = ""
    linkedin_post: str = ""
    twitter_thread: list[str] = Field(default_factory=list)
    instagram_caption: str = ""
    newsletter_summary: str = ""


class RepurposePlan(BaseModel):
    """Canonical repurpose plan — includes requested public output surface."""

    source_kind: str = ""
    reels: str = ""
    shorts: str = ""
    tiktok: str = ""
    blog_summary: str = ""
    linkedin_post: str = ""
    twitter_thread: list[str] = Field(default_factory=list)
    instagram_caption: str = ""
    newsletter_summary: str = ""
    platform: str = ""
    provider: str = "none"
    skipped: bool = False
    notes: str = ""


class RepurposePack(BaseModel):
    source_label: str = ""
    plan: RepurposePlan = Field(default_factory=RepurposePlan)
    fallback: bool = False
    notes: str = ""
    created_at: datetime = Field(default_factory=_utc_now)


class RepurposeResult(BaseModel):
    repurpose_pack: RepurposePack
    repurpose_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "repurpose_pack": self.repurpose_pack.model_dump(mode="json"),
            "messages": list(self.messages),
        }

    def public_output(self) -> dict[str, Any]:
        p = self.repurpose_pack.plan
        return {
            "source_kind": p.source_kind,
            "reels": p.reels,
            "shorts": p.shorts,
            "tiktok": p.tiktok,
            "blog_summary": p.blog_summary,
            "linkedin_post": p.linkedin_post,
            "twitter_thread": list(p.twitter_thread),
            "instagram_caption": p.instagram_caption,
            "newsletter_summary": p.newsletter_summary,
        }
