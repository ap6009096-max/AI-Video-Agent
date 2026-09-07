"""Brand kit schemas — voice, identity, colors, CTA, messaging."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BrandVoice(BaseModel):
    tone: str = ""
    personality: str = ""
    formality: str = ""
    do: list[str] = Field(default_factory=list)
    dont: list[str] = Field(default_factory=list)


class VisualIdentity(BaseModel):
    logo_treatment: str = ""
    typography: str = ""
    imagery_style: str = ""
    iconography: str = ""
    avoid: str = ""


class ColorTheme(BaseModel):
    name: str = ""
    primary: str = ""
    secondary: str = ""
    accent: str = ""
    background: str = ""
    text: str = ""
    usage_notes: str = ""


class CtaStyle(BaseModel):
    style: str = ""
    preferred_phrases: list[str] = Field(default_factory=list)
    avoid_phrases: list[str] = Field(default_factory=list)
    placement_hint: str = ""


class Messaging(BaseModel):
    tagline: str = ""
    pillars: list[str] = Field(default_factory=list)
    value_props: list[str] = Field(default_factory=list)
    banned_claims: list[str] = Field(default_factory=list)
    audience_promise: str = ""


class GeminiBrandBatch(BaseModel):
    """Optional Gemini enrichments for voice / CTA / messaging text."""

    tone: str = ""
    personality: str = ""
    tagline: str = ""
    preferred_phrases: list[str] = Field(default_factory=list)
    pillars: list[str] = Field(default_factory=list)
    notes: str = ""


class BrandPlan(BaseModel):
    brand_name: str = ""
    voice: BrandVoice = Field(default_factory=BrandVoice)
    visual_identity: VisualIdentity = Field(default_factory=VisualIdentity)
    colors: ColorTheme = Field(default_factory=ColorTheme)
    cta: CtaStyle = Field(default_factory=CtaStyle)
    messaging: Messaging = Field(default_factory=Messaging)
    provider: str = "none"
    skipped: bool = False
    notes: str = ""


class BrandPack(BaseModel):
    source_label: str = ""
    plan: BrandPlan = Field(default_factory=BrandPlan)
    fallback: bool = False
    notes: str = ""
    created_at: datetime = Field(default_factory=_utc_now)


class BrandResult(BaseModel):
    brand_pack: BrandPack
    brand_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "brand_pack": self.brand_pack.model_dump(mode="json"),
            "messages": list(self.messages),
        }

    def public_output(self) -> dict[str, Any]:
        p = self.brand_pack.plan
        return {
            "voice": p.voice.model_dump(),
            "visual_identity": p.visual_identity.model_dump(),
            "colors": p.colors.model_dump(),
            "cta": p.cta.model_dump(),
            "messaging": p.messaging.model_dump(),
        }
