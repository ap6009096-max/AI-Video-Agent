"""Localization schemas for country/region/language adaptation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LocalizationTarget(BaseModel):
    """One country/region/language triple to localize into."""

    country: str = ""
    region: str = ""
    language: str = ""


class CurrencyInfo(BaseModel):
    code: str = ""
    symbol: str = ""
    example: str = ""


class CountryProfile(BaseModel):
    id: str = ""
    name: str = ""
    default_language: str = "English"
    currency: CurrencyInfo = Field(default_factory=CurrencyInfo)
    measurements: Literal["metric", "imperial"] | str = "metric"
    date_format: str = "YYYY-MM-DD"
    cultural_notes: str = ""
    voice_hints: str = ""
    example_swaps: dict[str, str] = Field(default_factory=dict)


class RegionProfile(BaseModel):
    id: str = ""
    country_id: str = ""
    name: str = ""
    language: str = ""
    slang_notes: str = ""
    idioms: list[str] = Field(default_factory=list)
    humor_notes: str = ""
    cultural_notes: str = ""


class LanguageProfile(BaseModel):
    id: str = ""
    name: str = ""
    code: str = "en"
    script_direction: str = "ltr"
    formality: str = "neutral"
    vocabulary_notes: str = ""
    slang_notes: str = ""
    idiom_examples: list[str] = Field(default_factory=list)
    cta_style: str = ""
    caption_style: str = ""
    voice_notes: str = ""


class LocalePack(BaseModel):
    """Merged country + region + language adaptation context."""

    target: LocalizationTarget = Field(default_factory=LocalizationTarget)
    country: CountryProfile | None = None
    region: RegionProfile | None = None
    language: LanguageProfile | None = None
    include_regional_humor: bool = False
    voice: str = "Neutral"
    audience: str = "General"
    humor_adaptation: str = "none"
    humor_style: str = "None"
    cultural_summary: str = ""
    humor_summary: str = ""
    summary_notes: list[str] = Field(default_factory=list)


CulturalFindingKind = Literal[
    "reference",
    "idiom",
    "meme",
    "sarcasm",
    "reaction",
    "social_context",
    "example",
    "humor",
]

HumorStrategy = Literal[
    "keep",
    "adapt",
    "neutralize",
    "drop_joke_keep_meaning",
]


class CulturalFinding(BaseModel):
    clip_id: int = 0
    kind: CulturalFindingKind | str = "reference"
    source_span: str = ""
    risk: str = ""
    recommendation: str = ""
    local_equivalent: str = ""


class CulturalAdaptationReport(BaseModel):
    project_id: str
    audience: str = "General"
    target: LocalizationTarget = Field(default_factory=LocalizationTarget)
    findings: list[CulturalFinding] = Field(default_factory=list)
    provider: str = "gemini-cultural"
    created_at: datetime = Field(default_factory=_utc_now)
    notes: str = ""
    cultural_summary: str = ""


class CulturalAdaptationResult(BaseModel):
    cultural_adaptation: CulturalAdaptationReport
    cultural_adaptation_path: str
    locale_pack: LocalePack | None = None
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "cultural_adaptation": self.cultural_adaptation.model_dump(mode="json"),
            "locale_pack": (
                self.locale_pack.model_dump(mode="json") if self.locale_pack else None
            ),
            "messages": list(self.messages),
        }


class HumorPlanItem(BaseModel):
    clip_id: int = 0
    source_humor_present: bool = False
    strategy: HumorStrategy | str = "keep"
    rationale: str = ""
    suggested_approach: str = ""


class HumorLocalizationReport(BaseModel):
    project_id: str
    mode: str = "none"
    humor_style: str = "None"
    audience: str = "General"
    items: list[HumorPlanItem] = Field(default_factory=list)
    provider: str = "gemini-humor"
    created_at: datetime = Field(default_factory=_utc_now)
    notes: str = ""
    humor_summary: str = ""


class HumorLocalizationResult(BaseModel):
    humor_localization: HumorLocalizationReport
    humor_localization_path: str
    locale_pack: LocalePack | None = None
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "humor_localization": self.humor_localization.model_dump(mode="json"),
            "locale_pack": (
                self.locale_pack.model_dump(mode="json") if self.locale_pack else None
            ),
            "messages": list(self.messages),
        }


class GeminiCulturalFinding(BaseModel):
    clip_id: int = 0
    kind: str = "reference"
    source_span: str = ""
    risk: str = ""
    recommendation: str = ""
    local_equivalent: str = ""


class GeminiCulturalBatch(BaseModel):
    findings: list[GeminiCulturalFinding] = Field(default_factory=list)
    cultural_summary: str = ""


class GeminiHumorPlanItem(BaseModel):
    clip_id: int = 0
    source_humor_present: bool = False
    strategy: str = "keep"
    rationale: str = ""
    suggested_approach: str = ""


class GeminiHumorBatch(BaseModel):
    items: list[GeminiHumorPlanItem] = Field(default_factory=list)
    humor_summary: str = ""


class LocalizedClipScript(BaseModel):
    """Localized publishable script for one clip."""

    clip_id: int = 0
    title: str = ""
    hook: str = ""
    short_script: str = ""
    caption: str = ""
    cta: str = ""
    thumbnail_text: str = ""
    keywords: list[str] = Field(default_factory=list)
    voice_direction: str = ""
    locale: LocalizationTarget = Field(default_factory=LocalizationTarget)


class LocalizedVersion(BaseModel):
    """One localized version of all clip scripts."""

    target: LocalizationTarget = Field(default_factory=LocalizationTarget)
    locale_pack: LocalePack = Field(default_factory=LocalePack)
    scripts: list[LocalizedClipScript] = Field(default_factory=list)


class LocalizationReport(BaseModel):
    project_id: str
    versions: list[LocalizedVersion] = Field(default_factory=list)
    provider: str = "gemini-localization"
    created_at: datetime = Field(default_factory=_utc_now)
    notes: str = ""


class LocalizationResult(BaseModel):
    localizations: LocalizationReport
    localizations_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "localizations": self.localizations.model_dump(mode="json"),
            "messages": list(self.messages),
        }


class CountryAgentResult(BaseModel):
    country_profile: CountryProfile | None = None
    locale_context_path: str = ""
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "country_profile": (
                self.country_profile.model_dump(mode="json")
                if self.country_profile
                else None
            ),
            "messages": list(self.messages),
        }


class RegionalAgentResult(BaseModel):
    region_profile: RegionProfile | None = None
    locale_pack: LocalePack | None = None
    locale_context_path: str = ""
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "region_profile": (
                self.region_profile.model_dump(mode="json")
                if self.region_profile
                else None
            ),
            "locale_pack": (
                self.locale_pack.model_dump(mode="json") if self.locale_pack else None
            ),
            "messages": list(self.messages),
        }


class GeminiLocalizedClip(BaseModel):
    clip_id: int = 0
    title: str = ""
    hook: str = ""
    short_script: str = ""
    caption: str = ""
    cta: str = ""
    thumbnail_text: str = ""
    keywords: list[str] = Field(default_factory=list)
    voice_direction: str = ""


class GeminiLocalizedBatch(BaseModel):
    scripts: list[GeminiLocalizedClip] = Field(default_factory=list)
