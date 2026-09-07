"""Story and Script agent schemas (post-clip creative layer)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StoryStructure(BaseModel):
    """Short-form beat sheet: HOOK → CONTEXT → VALUE/EVENT → PAYOFF → CTA."""

    hook: str = ""
    context: str = ""
    value_event: str = ""
    payoff: str = ""
    cta: str = ""


class ClipStory(BaseModel):
    """Story structure for one selected clip."""

    clip_id: int = 0
    start: float = 0.0
    end: float = 0.0
    structure: StoryStructure = Field(default_factory=StoryStructure)
    source_excerpt: str = ""


class ClipScript(BaseModel):
    """Publishable script package for one selected clip."""

    clip_id: int = 0
    title: str = ""
    hook: str = ""
    short_script: str = ""
    caption: str = ""
    cta: str = ""
    thumbnail_text: str = ""
    keywords: list[str] = Field(default_factory=list)
    story_structure: StoryStructure = Field(default_factory=StoryStructure)


class GeminiClipStory(BaseModel):
    """Lean Gemini output for one clip story."""

    clip_id: int = 0
    hook: str = ""
    context: str = ""
    value_event: str = ""
    payoff: str = ""
    cta: str = ""


class GeminiStoriesBatch(BaseModel):
    """Batch Gemini output for Story Agent."""

    stories: list[GeminiClipStory] = Field(default_factory=list)


class GeminiClipScript(BaseModel):
    """Lean Gemini output for one clip script package."""

    clip_id: int = 0
    title: str = ""
    hook: str = ""
    short_script: str = ""
    caption: str = ""
    cta: str = ""
    thumbnail_text: str = ""
    keywords: list[str] = Field(default_factory=list)


class GeminiScriptsBatch(BaseModel):
    """Batch Gemini output for Script Agent."""

    scripts: list[GeminiClipScript] = Field(default_factory=list)


class StoriesReport(BaseModel):
    project_id: str
    stories: list[ClipStory] = Field(default_factory=list)
    provider: str = "gemini-story"
    created_at: datetime = Field(default_factory=_utc_now)
    notes: str = ""


class ScriptsReport(BaseModel):
    project_id: str
    scripts: list[ClipScript] = Field(default_factory=list)
    provider: str = "gemini-script"
    created_at: datetime = Field(default_factory=_utc_now)
    notes: str = ""


class StoryAgentResult(BaseModel):
    stories: StoriesReport
    stories_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "stories": self.stories.model_dump(mode="json"),
            "messages": list(self.messages),
        }


class ScriptAgentResult(BaseModel):
    scripts: ScriptsReport
    scripts_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "scripts": self.scripts.model_dump(mode="json"),
            "messages": list(self.messages),
        }
