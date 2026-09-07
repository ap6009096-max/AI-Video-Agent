"""Character management schemas (Prompt 40) — cast bible for consistency."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


CharacterRoleType = Literal[
    "human", "narrator", "ai_avatar", "mascot", "animated"
]


class CharacterProfile(BaseModel):
    """One cast member identity for cross-scene consistency."""

    name: str = ""
    role_type: CharacterRoleType = "human"
    appearance: str = ""
    clothing: str = ""
    voice: str = ""
    personality: str = ""
    expressions: list[str] = Field(default_factory=list)
    scene_ids: list[int] = Field(default_factory=list)


class GeminiCharacterBatch(BaseModel):
    """Structured Gemini output for character planning."""

    characters: list[CharacterProfile] = Field(default_factory=list)
    consistency_notes: list[str] = Field(default_factory=list)
    notes: str = ""


class CharacterPlan(BaseModel):
    """Canonical plan written to analysis/character_plan.json."""

    characters: list[CharacterProfile] = Field(default_factory=list)
    consistency_notes: list[str] = Field(default_factory=list)
    provider: str = "none"
    skipped: bool = False
    notes: str = ""


class CharacterPack(BaseModel):
    source_label: str = ""
    plan: CharacterPlan = Field(default_factory=CharacterPlan)
    fallback: bool = False
    notes: str = ""
    created_at: datetime = Field(default_factory=_utc_now)


class CharacterResult(BaseModel):
    character_pack: CharacterPack
    character_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "character_pack": self.character_pack.model_dump(mode="json"),
            "messages": list(self.messages),
        }

    def public_output(self) -> dict[str, Any]:
        """Requested public cast bible surface."""
        return {
            "characters": [
                {
                    "name": c.name,
                    "role_type": c.role_type,
                    "appearance": c.appearance,
                    "clothing": c.clothing,
                    "voice": c.voice,
                    "personality": c.personality,
                    "expressions": list(c.expressions),
                }
                for c in self.character_pack.plan.characters
            ],
            "consistency_notes": list(self.character_pack.plan.consistency_notes),
        }
