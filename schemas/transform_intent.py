"""Selective scene transform intent (Phase 1) — changed vs preserved."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


RegenScope = Literal[
    "dialogue",
    "voice",
    "captions",
    "trim",
    "reframe",
    "video",
]

PreservedElement = Literal[
    "host",
    "guest",
    "background",
    "music",
    "camera",
    "other_scenes",
    "captions",
    "voice",
    "visuals",
]


class TransformIntent(BaseModel):
    """Structured NL edit request for one scene (or a small set)."""

    target_scene: int | str = 1
    target_speaker: str = ""
    instruction: str = ""
    requested_changes: list[str] = Field(default_factory=list)
    preserved_elements: list[str] = Field(default_factory=list)
    regeneration_scope: list[str] = Field(default_factory=list)
    unsupported_changes: list[str] = Field(default_factory=list)
    output_requirements: list[str] = Field(default_factory=lambda: ["playable mp4"])
    start_seconds: float = 0.0
    end_seconds: float = 0.0
    scenes_total: int = 0
    scenes_changed: int = 1
    notes: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def scenes_preserved(self) -> int:
        total = max(0, int(self.scenes_total or 0))
        changed = max(0, int(self.scenes_changed or 0))
        if total <= 0:
            return max(0, 0 if changed else 0)
        return max(0, total - changed)


class GeminiTransformBatch(BaseModel):
    """Structured Gemini output for transform intent."""

    target_scene: int | str = 1
    target_speaker: str = ""
    requested_changes: list[str] = Field(default_factory=list)
    preserved_elements: list[str] = Field(default_factory=list)
    regeneration_scope: list[str] = Field(default_factory=list)
    unsupported_changes: list[str] = Field(default_factory=list)
    notes: str = ""


class TransformIntentPlan(BaseModel):
    """Canonical plan written to analysis/transform_intent.json."""

    intent: TransformIntent = Field(default_factory=TransformIntent)
    provider: str = "none"
    skipped: bool = False
    applied: bool = False
    notes: str = ""


class TransformIntentPack(BaseModel):
    source_label: str = ""
    plan: TransformIntentPlan = Field(default_factory=TransformIntentPlan)
    fallback: bool = False
    notes: str = ""
    created_at: datetime = Field(default_factory=_utc_now)


class TransformIntentResult(BaseModel):
    transform_intent_pack: TransformIntentPack
    transform_intent_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "transform_intent_pack": self.transform_intent_pack.model_dump(mode="json"),
            "messages": list(self.messages),
        }

    def public_output(self) -> dict[str, Any]:
        intent = self.transform_intent_pack.plan.intent
        return {
            "target_scene": intent.target_scene,
            "target_speaker": intent.target_speaker,
            "requested_changes": list(intent.requested_changes),
            "preserved_elements": list(intent.preserved_elements),
            "regeneration_scope": list(intent.regeneration_scope),
            "unsupported_changes": list(intent.unsupported_changes),
            "output_requirements": list(intent.output_requirements),
            "scenes_total": intent.scenes_total,
            "scenes_changed": intent.scenes_changed,
            "scenes_preserved": intent.scenes_preserved,
            "changed_summary": (
                f"Changed {intent.scenes_changed} of {intent.scenes_total} scenes"
                if intent.scenes_total
                else f"Changed {intent.scenes_changed} scene(s)"
            ),
            "skipped": self.transform_intent_pack.plan.skipped,
        }
