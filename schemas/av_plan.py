"""A/V planning schemas for B-roll, voice, and music agents."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


BRollSourceKind = Literal[
    "source_footage",
    "user_provided",
    "external_required",
    "generated_required",
    "placeholder",
]

VoiceMode = Literal["original", "ai_tts", "talent_direction"]
MusicMode = Literal["original", "none", "bed"]


# --- B-Roll ---


class BRollTemplate(BaseModel):
    id: str = ""
    name: str = ""
    aliases: list[str] = Field(default_factory=list)
    description: str = ""
    default_source_kind: BRollSourceKind | str = "placeholder"
    notes: str = ""


class BRollItem(BaseModel):
    clip_id: int = 0
    description: str = ""
    start_hint: float | None = None
    end_hint: float | None = None
    source_kind: BRollSourceKind | str = "placeholder"
    available: bool = False
    asset_path: str = ""
    template_id: str = ""
    notes: str = ""


class BRollPlan(BaseModel):
    project_id: str = ""
    items: list[BRollItem] = Field(default_factory=list)
    skipped: bool = False
    notes: str = ""
    created_at: datetime = Field(default_factory=_utc_now)


class BRollPack(BaseModel):
    plan: BRollPlan = Field(default_factory=BRollPlan)
    notes: str = ""
    created_at: datetime = Field(default_factory=_utc_now)


class BRollResult(BaseModel):
    broll_pack: BRollPack
    broll_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "broll_pack": self.broll_pack.model_dump(mode="json"),
            "messages": list(self.messages),
        }


# --- Voice ---


class VoicePreset(BaseModel):
    id: str = ""
    name: str = ""
    aliases: list[str] = Field(default_factory=list)
    mode: VoiceMode | str = "original"
    gender: str = ""
    language_hint: str = ""
    notes: str = ""


class LocalizedVoiceTrack(BaseModel):
    language: str = ""
    language_code: str = ""
    voice_id: str = ""
    text: str = ""
    audio_path: str = ""
    duration_sec: float = 0.0
    provider: str = ""
    ok: bool = False
    error: str | None = None
    accent: str = ""
    emotion: str = "neutral"
    rate: str = "+0%"
    pitch: str = "+0Hz"


class VoicePlan(BaseModel):
    preset_name: str = ""
    mode: VoiceMode | str = "original"
    preserve_original: bool = True
    provider: str = ""
    provider_ready: bool = False
    gender: str = ""
    language_hint: str = ""
    language_code: str = ""
    provider_voice_id: str = ""
    accent: str = ""
    emotion: str = "neutral"
    speaking_rate: float = 1.0
    pitch: float = 1.0
    rate: str = "+0%"
    pitch_ssml: str = "+0Hz"
    volume: str = "+0%"
    direction: str = ""
    audio_path: str = ""
    primary_audio_path: str = ""
    tracks: list[LocalizedVoiceTrack] = Field(default_factory=list)
    notes: str = ""


class VoicePack(BaseModel):
    source_label: str = ""
    preset: VoicePreset = Field(default_factory=VoicePreset)
    plan: VoicePlan = Field(default_factory=VoicePlan)
    fallback: bool = False
    notes: str = ""
    created_at: datetime = Field(default_factory=_utc_now)


class VoiceResult(BaseModel):
    voice_pack: VoicePack
    voice_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "voice_pack": self.voice_pack.model_dump(mode="json"),
            "messages": list(self.messages),
        }


# --- Music ---


class MusicPreset(BaseModel):
    id: str = ""
    name: str = ""
    aliases: list[str] = Field(default_factory=list)
    mode: MusicMode | str = "original"
    mood: str = ""
    energy: str = ""
    notes: str = ""
    generation_required: bool = False


class MusicPlan(BaseModel):
    preset_name: str = ""
    mode: MusicMode | str = "original"
    mood: str = ""
    energy: str = ""
    generation_required: bool = False
    asset_path: str = ""
    skipped: bool = False
    notes: str = ""


class MusicPack(BaseModel):
    source_label: str = ""
    preset: MusicPreset = Field(default_factory=MusicPreset)
    plan: MusicPlan = Field(default_factory=MusicPlan)
    fallback: bool = False
    notes: str = ""
    created_at: datetime = Field(default_factory=_utc_now)


class MusicResult(BaseModel):
    music_pack: MusicPack
    music_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "music_pack": self.music_pack.model_dump(mode="json"),
            "messages": list(self.messages),
        }
