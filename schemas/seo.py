"""SEO / metadata planning schemas (Prompt 31)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SeoPreset(BaseModel):
    id: str = ""
    name: str = ""
    aliases: list[str] = Field(default_factory=list)
    max_title_chars: int = 100
    max_description_chars: int = 5000
    max_hashtags: int = 8
    max_tags: int = 12
    max_keywords: int = 15
    notes: str = ""


class SeoPlan(BaseModel):
    """Canonical SEO plan — includes requested public output surface."""

    title: str = ""
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    hashtags: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    platform: str = ""
    skipped: bool = False
    notes: str = ""


class SeoPack(BaseModel):
    source_label: str = ""
    preset: SeoPreset = Field(default_factory=SeoPreset)
    plan: SeoPlan = Field(default_factory=SeoPlan)
    fallback: bool = False
    notes: str = ""
    created_at: datetime = Field(default_factory=_utc_now)


class SeoResult(BaseModel):
    seo_pack: SeoPack
    seo_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "seo_pack": self.seo_pack.model_dump(mode="json"),
            "messages": list(self.messages),
        }

    def public_output(self) -> dict[str, Any]:
        """Minimal requested output shape (includes tags)."""
        p = self.seo_pack.plan
        return {
            "title": p.title,
            "description": p.description,
            "tags": list(p.tags),
            "hashtags": list(p.hashtags),
            "keywords": list(p.keywords),
        }
