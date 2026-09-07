"""Caption planning and export schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


CaptionLevel = Literal["word", "sentence"]
CaptionAnimation = Literal[
    "none",
    "word_highlight",
    "pop",
    "bounce",
    "zoom",
    "karaoke",
]
CaptionDirection = Literal["ltr", "rtl"]


class AssStyleConfig(BaseModel):
    font: str = "Arial"
    size: int = 48
    bold: bool = True
    outline: int = 3
    shadow: int = 1
    primary_color: str = "&H00FFFFFF"
    highlight_color: str = "&H0000FFFF"
    outline_color: str = "&H00000000"
    back_color: str = "&H80000000"


class CaptionStylePreset(BaseModel):
    id: str = ""
    name: str = ""
    aliases: list[str] = Field(default_factory=list)
    ass_style: AssStyleConfig = Field(default_factory=AssStyleConfig)
    animation: CaptionAnimation | str = "none"
    effects: list[str] = Field(default_factory=list)
    max_chars_per_line: int = 32
    max_lines: int = 2
    emoji_allowed: bool = False
    notes: str = ""


class PlatformSafeArea(BaseModel):
    id: str = ""
    name: str = ""
    aliases: list[str] = Field(default_factory=list)
    margin_l: int = 40
    margin_r: int = 40
    margin_v: int = 120
    alignment: int = 2
    notes: str = ""


class CaptionWord(BaseModel):
    word: str = ""
    start: float
    end: float
    highlighted: bool = False


class CaptionCue(BaseModel):
    level: CaptionLevel | str = "sentence"
    start: float
    end: float
    text: str = ""
    highlighted_tokens: list[str] = Field(default_factory=list)
    emoji: str = ""
    words: list[CaptionWord] = Field(default_factory=list)


class CaptionTrack(BaseModel):
    language: str = ""
    direction: CaptionDirection | str = "ltr"
    localized: bool = False
    cues: list[CaptionCue] = Field(default_factory=list)


class CaptionPlan(BaseModel):
    project_id: str = ""
    timed: bool = False
    skipped: bool = False
    style_name: str = ""
    platform: str = ""
    emoji_enabled: bool = False
    burn_in_requested: bool = False
    burn_in_applied: bool = False
    notes: str = ""
    created_at: datetime = Field(default_factory=_utc_now)


class CaptionPack(BaseModel):
    plan: CaptionPlan = Field(default_factory=CaptionPlan)
    style: CaptionStylePreset = Field(default_factory=CaptionStylePreset)
    safe_area: PlatformSafeArea = Field(default_factory=PlatformSafeArea)
    primary_track: CaptionTrack = Field(default_factory=CaptionTrack)
    localized_track: CaptionTrack | None = None
    word_cues: list[CaptionCue] = Field(default_factory=list)
    sentence_cues: list[CaptionCue] = Field(default_factory=list)
    srt_path: str = ""
    vtt_path: str = ""
    ass_path: str = ""
    burned_in_path: str = ""
    notes: str = ""
    created_at: datetime = Field(default_factory=_utc_now)


class CaptionResult(BaseModel):
    captions_pack: CaptionPack
    captions_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "captions_pack": self.captions_pack.model_dump(mode="json"),
            "messages": list(self.messages),
        }
