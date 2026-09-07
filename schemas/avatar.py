"""Avatar planning schemas (Prompt 28)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AvatarPreset(BaseModel):
    id: str = ""
    name: str = ""
    aliases: list[str] = Field(default_factory=list)
    gender_hint: str = ""
    default_expression: str = "neutral"
    default_gesture: str = "none"
    lip_sync_default: bool = False
    eye_contact_default: bool = False
    notes: str = ""


class AvatarPlan(BaseModel):
    """Canonical avatar plan — includes requested output surface."""

    avatar_type: str = ""
    voice: str = ""
    language: str = ""
    emotion: str = ""
    lip_sync: bool = False
    gesture: str = "none"
    eye_contact: bool = False
    expression: str = "neutral"
    speaking_language_code: str = ""
    audio_path: str = ""
    provider: str = "none"
    provider_ready: bool = False
    skipped: bool = False
    gender_hint: str = ""
    custom: bool = False
    notes: str = ""


class AvatarPack(BaseModel):
    source_label: str = ""
    preset: AvatarPreset = Field(default_factory=AvatarPreset)
    plan: AvatarPlan = Field(default_factory=AvatarPlan)
    fallback: bool = False
    notes: str = ""
    created_at: datetime = Field(default_factory=_utc_now)


class AvatarResult(BaseModel):
    avatar_pack: AvatarPack
    avatar_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "avatar_pack": self.avatar_pack.model_dump(mode="json"),
            "messages": list(self.messages),
        }

    def public_output(self) -> dict[str, str]:
        """Minimal requested output shape."""
        p = self.avatar_pack.plan
        return {
            "avatar_type": p.avatar_type,
            "voice": p.voice,
            "language": p.language,
            "emotion": p.emotion,
        }
