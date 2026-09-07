"""Load and resolve voice presets from config/voices.json."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from schemas.av_plan import VoicePack, VoicePlan, VoicePreset
from tools.voice.locale_map import normalize_language, resolve_edge_voice
from tools.voice.prosody import build_prosody
from tools.voice.provider import get_tts_provider

_CATALOG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "voices.json"


def _norm(value: str) -> str:
    return " ".join(
        (value or "").strip().lower().replace("_", " ").replace("-", " ").split()
    )


@lru_cache(maxsize=1)
def _load_raw() -> list[dict[str, Any]]:
    return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))


def clear_voice_cache() -> None:
    _load_raw.cache_clear()


def list_voices() -> list[VoicePreset]:
    return [VoicePreset.model_validate(item) for item in _load_raw()]


def resolve_voice(name_or_id: str) -> VoicePreset | None:
    key = _norm(name_or_id)
    if not key:
        return None
    for preset in list_voices():
        if _norm(preset.id) == key or _norm(preset.name) == key:
            return preset
        for alias in preset.aliases:
            if _norm(alias) == key:
                return preset
    return None


def _fallback_preset(label: str) -> VoicePreset:
    return VoicePreset(
        id="fallback_original",
        name=label.strip() or "Original Voice",
        mode="original",
        notes="Unknown voice label — falling back to original audio.",
    )


def build_voice_pack(
    voice_label: str,
    *,
    language: str = "",
    country: str = "",
    enabled: bool = True,
    emotion: str = "neutral",
    speed: float = 1.0,
    pitch: float = 1.0,
) -> VoicePack:
    label = (voice_label or "").strip() or "Original Voice"
    preset = resolve_voice(label)
    fallback = False
    if preset is None:
        preset = _fallback_preset(label)
        fallback = True

    provider = get_tts_provider()
    real_tts = provider.name != "passthrough" and provider.is_available()

    preserve = True
    notes_parts: list[str] = []
    if not enabled:
        notes_parts.append("Voice feature flag off — preserving original audio.")
        preserve = True
    elif preset.mode == "original" or fallback:
        notes_parts.append("Original voice mode — preserving source audio.")
        preserve = True
    elif preset.mode in ("ai_tts", "talent_direction") and not real_tts:
        notes_parts.append(
            f"Voice '{preset.name}' requested but no TTS provider configured "
            "— preserving original audio."
        )
        preserve = True
    elif real_tts and preset.mode in ("ai_tts", "talent_direction"):
        preserve = False
        notes_parts.append(f"TTS provider '{provider.name}' ready for synthesis.")
    else:
        notes_parts.append(f"Voice '{preset.name}' planned.")
        preserve = True

    lang = (preset.language_hint or language or "").strip()
    lang_code = normalize_language(lang or language or "en")
    gender = (preset.gender or "neutral").strip() or "neutral"
    voice_id = resolve_edge_voice(lang_code, gender, country)
    prosody = build_prosody(emotion=emotion, speed=speed, pitch=pitch)
    accent = country.strip() if country else ""

    direction = (
        f"{gender} voice"
        + (f", language={lang or lang_code}" if (lang or lang_code) else "")
        + (f", accent={accent}" if accent else "")
        + f", {prosody['note']}"
        + (f". {preset.notes}" if preset.notes else "")
    ).strip()

    plan = VoicePlan(
        preset_name=preset.name,
        mode=preset.mode,
        preserve_original=preserve,
        provider=provider.name,
        provider_ready=real_tts,
        gender=gender,
        language_hint=lang,
        language_code=lang_code,
        provider_voice_id=voice_id,
        accent=accent,
        emotion=str(prosody["emotion"]),
        speaking_rate=float(prosody["speaking_rate"]),
        pitch=float(prosody["pitch"]),
        rate=str(prosody["rate"]),
        pitch_ssml=str(prosody["pitch_ssml"]),
        volume=str(prosody["volume"]),
        direction=direction,
        audio_path="",
        primary_audio_path="",
        tracks=[],
        notes=" ".join(notes_parts),
    )
    return VoicePack(
        source_label=label,
        preset=preset,
        plan=plan,
        fallback=fallback,
        notes=plan.notes,
    )
