"""Brand preset catalog and pack builder."""

from __future__ import annotations

import json
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

from config.settings import get_settings
from schemas.brand import (
    BrandPack,
    BrandPlan,
    BrandVoice,
    ColorTheme,
    CtaStyle,
    GeminiBrandBatch,
    Messaging,
    VisualIdentity,
)
from schemas.job import VideoJobConfig

_CATALOG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "brands.json"

EnrichFn = Callable[..., GeminiBrandBatch]


def _norm(value: str) -> str:
    return " ".join(
        (value or "").strip().lower().replace("_", " ").replace("-", " ").split()
    )


@lru_cache(maxsize=1)
def _load_raw() -> list[dict[str, Any]]:
    return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))


def clear_brand_cache() -> None:
    _load_raw.cache_clear()


def list_brand_presets() -> list[dict[str, Any]]:
    return list(_load_raw())


def resolve_brand_preset(name_or_id: str) -> dict[str, Any] | None:
    key = _norm(name_or_id)
    if not key:
        return None
    for item in list_brand_presets():
        if _norm(str(item.get("id") or "")) == key or _norm(str(item.get("name") or "")) == key:
            return item
        for alias in item.get("aliases") or []:
            if _norm(str(alias)) == key:
                return item
    for item in list_brand_presets():
        pname = _norm(str(item.get("name") or ""))
        if pname and (key.startswith(pname) or pname in key):
            return item
    return None


def _fallback_generic() -> dict[str, Any]:
    return resolve_brand_preset("Generic Creator") or {
        "id": "generic_creator",
        "name": "Generic Creator",
        "voice": {
            "tone": "friendly",
            "personality": "helpful creator",
            "formality": "casual",
            "do": ["Be clear"],
            "dont": ["Overpromise"],
        },
        "visual_identity": {
            "logo_treatment": "Simple end-card mark",
            "typography": "Bold sans-serif",
            "imagery_style": "Bright lifestyle",
            "iconography": "Minimal icons",
            "avoid": "Trademarked looks",
        },
        "colors": {
            "name": "Creator Bright",
            "primary": "#2563EB",
            "secondary": "#0EA5E9",
            "accent": "#F59E0B",
            "background": "#0F172A",
            "text": "#F8FAFC",
            "usage_notes": "High contrast titles and CTAs",
        },
        "cta": {
            "style": "soft",
            "preferred_phrases": ["Follow for more"],
            "avoid_phrases": ["Guaranteed results"],
            "placement_hint": "After payoff",
        },
        "messaging": {
            "tagline": "Make better videos, faster",
            "pillars": ["Clarity", "Consistency"],
            "value_props": ["Practical tips"],
            "banned_claims": ["Guaranteed viral"],
            "audience_promise": "One actionable tip per video",
        },
        "notes": "Hardcoded fallback.",
    }


def _as_list(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    return []


def _voice_from(raw: dict[str, Any] | None) -> BrandVoice:
    raw = raw if isinstance(raw, dict) else {}
    return BrandVoice(
        tone=str(raw.get("tone") or "").strip(),
        personality=str(raw.get("personality") or "").strip(),
        formality=str(raw.get("formality") or "").strip(),
        do=_as_list(raw.get("do")),
        dont=_as_list(raw.get("dont")),
    )


def _identity_from(raw: dict[str, Any] | None) -> VisualIdentity:
    raw = raw if isinstance(raw, dict) else {}
    return VisualIdentity(
        logo_treatment=str(raw.get("logo_treatment") or "").strip(),
        typography=str(raw.get("typography") or "").strip(),
        imagery_style=str(raw.get("imagery_style") or "").strip(),
        iconography=str(raw.get("iconography") or "").strip(),
        avoid=str(raw.get("avoid") or "").strip(),
    )


def _colors_from(raw: dict[str, Any] | None) -> ColorTheme:
    raw = raw if isinstance(raw, dict) else {}
    return ColorTheme(
        name=str(raw.get("name") or "").strip(),
        primary=str(raw.get("primary") or "").strip(),
        secondary=str(raw.get("secondary") or "").strip(),
        accent=str(raw.get("accent") or "").strip(),
        background=str(raw.get("background") or "").strip(),
        text=str(raw.get("text") or "").strip(),
        usage_notes=str(raw.get("usage_notes") or "").strip(),
    )


def _cta_from(raw: dict[str, Any] | None) -> CtaStyle:
    raw = raw if isinstance(raw, dict) else {}
    return CtaStyle(
        style=str(raw.get("style") or "").strip(),
        preferred_phrases=_as_list(raw.get("preferred_phrases")),
        avoid_phrases=_as_list(raw.get("avoid_phrases")),
        placement_hint=str(raw.get("placement_hint") or "").strip(),
    )


def _messaging_from(raw: dict[str, Any] | None) -> Messaging:
    raw = raw if isinstance(raw, dict) else {}
    return Messaging(
        tagline=str(raw.get("tagline") or "").strip(),
        pillars=_as_list(raw.get("pillars")),
        value_props=_as_list(raw.get("value_props")),
        banned_claims=_as_list(raw.get("banned_claims")),
        audience_promise=str(raw.get("audience_promise") or "").strip(),
    )


def brand_constraint_notes(brand_pack: dict[str, Any] | None) -> str:
    """Short constraint block for downstream marketing agents."""
    if not isinstance(brand_pack, dict):
        return ""
    plan = brand_pack.get("plan") or {}
    if not isinstance(plan, dict) or plan.get("skipped"):
        return ""
    voice = plan.get("voice") or {}
    cta = plan.get("cta") or {}
    messaging = plan.get("messaging") or {}
    colors = plan.get("colors") or {}
    name = str(plan.get("brand_name") or "").strip() or "Brand"
    bits = [
        f"Brand={name}",
        f"voice={voice.get('tone') or ''}".strip("="),
        f"cta={cta.get('style') or ''}",
    ]
    phrases = cta.get("preferred_phrases") or []
    if isinstance(phrases, list) and phrases:
        bits.append(f"CTA phrases: {', '.join(str(p) for p in phrases[:3])}")
    tagline = str(messaging.get("tagline") or "").strip()
    if tagline:
        bits.append(f"tagline: {tagline}")
    if colors.get("primary"):
        bits.append(f"primary={colors.get('primary')}")
    return " | ".join(b for b in bits if b and not b.endswith("="))


def _blend_visual_style_notes(
    colors: ColorTheme,
    visual_style_pack: dict[str, Any] | None,
) -> ColorTheme:
    if not isinstance(visual_style_pack, dict):
        return colors
    plan = visual_style_pack.get("plan") or {}
    if not isinstance(plan, dict):
        return colors
    palette = str(plan.get("color_palette") or "").strip()
    if not palette:
        return colors
    note = colors.usage_notes.strip()
    extra = f"Visual style palette hint: {palette}."
    usage = f"{note} {extra}".strip() if note else extra
    return colors.model_copy(update={"usage_notes": usage})


def build_brand_pack(
    *,
    enabled: bool = True,
    config: VideoJobConfig | None = None,
    platform_pack: dict[str, Any] | None = None,
    visual_style_pack: dict[str, Any] | None = None,
    enrich_fn: EnrichFn | None = None,
) -> BrandPack:
    job = config or VideoJobConfig()
    label = (
        (job.brand_preset or "").strip()
        or (job.brand_name or "").strip()
        or "Generic Creator"
    )
    preset = resolve_brand_preset(label)
    fallback = preset is None
    if preset is None:
        preset = _fallback_generic()

    brand_name = (job.brand_name or "").strip() or str(preset.get("name") or "Generic Creator")
    source_label = str(preset.get("name") or label)

    if not enabled:
        plan = BrandPlan(
            brand_name=brand_name,
            provider="none",
            skipped=True,
            notes="Brand feature flag off — skipped.",
        )
        return BrandPack(
            source_label=source_label,
            plan=plan,
            fallback=fallback,
            notes=plan.notes,
        )

    voice = _voice_from(preset.get("voice") if isinstance(preset, dict) else None)
    identity = _identity_from(
        preset.get("visual_identity") if isinstance(preset, dict) else None
    )
    colors = _blend_visual_style_notes(
        _colors_from(preset.get("colors") if isinstance(preset, dict) else None),
        visual_style_pack,
    )
    cta = _cta_from(preset.get("cta") if isinstance(preset, dict) else None)
    messaging = _messaging_from(
        preset.get("messaging") if isinstance(preset, dict) else None
    )

    # Soft blend platform CTA strategy into placement hint when empty
    if isinstance(platform_pack, dict) and not cta.placement_hint:
        pplan = platform_pack.get("plan") or {}
        if isinstance(pplan, dict):
            strat = str(pplan.get("cta_strategy") or "").strip()
            if strat:
                cta = cta.model_copy(update={"placement_hint": strat})

    provider = "heuristic"
    notes_extra = ""
    settings = get_settings()
    use_gemini = bool(enrich_fn is not None or settings.has_gemini_api_key)
    if use_gemini:
        try:
            from tools.llm.gemini import enrich_brand_kit

            fn = enrich_fn or enrich_brand_kit
            batch = fn(
                brand_name=brand_name,
                audience=job.audience or "General",
                platform=(job.platform or "YouTube"),
                tone=voice.tone,
                tagline=messaging.tagline,
                pillars=list(messaging.pillars),
            )
            updates_voice: dict[str, Any] = {}
            if batch.tone:
                updates_voice["tone"] = batch.tone.strip()
            if batch.personality:
                updates_voice["personality"] = batch.personality.strip()
            if updates_voice:
                voice = voice.model_copy(update=updates_voice)
            if batch.preferred_phrases:
                cta = cta.model_copy(
                    update={
                        "preferred_phrases": _as_list(batch.preferred_phrases)
                        or cta.preferred_phrases
                    }
                )
            msg_updates: dict[str, Any] = {}
            if batch.tagline:
                msg_updates["tagline"] = batch.tagline.strip()
            if batch.pillars:
                msg_updates["pillars"] = _as_list(batch.pillars) or messaging.pillars
            if msg_updates:
                messaging = messaging.model_copy(update=msg_updates)
            provider = "gemini"
            fallback = False
            if batch.notes:
                notes_extra = f" {batch.notes}"
        except Exception as exc:  # noqa: BLE001
            notes_extra = f" Gemini failed ({exc}); heuristic fallback."
            provider = "heuristic"
            fallback = True

    plan = BrandPlan(
        brand_name=brand_name,
        voice=voice,
        visual_identity=identity,
        colors=colors,
        cta=cta,
        messaging=messaging,
        provider=provider,
        skipped=False,
        notes=(
            f"Brand kit for {brand_name} via {provider}."
            f"{notes_extra} Plan only (MVP)."
        ),
    )
    return BrandPack(
        source_label=source_label,
        plan=plan,
        fallback=fallback,
        notes=plan.notes,
    )
