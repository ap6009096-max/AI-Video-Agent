"""Resolve edge-tts voices from language, gender, and country accent."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent.parent
_LOCALES_PATH = _ROOT / "config" / "voices_locales.json"
_ACCENTS_PATH = _ROOT / "config" / "voices_accents.json"

SUPPORTED_VOICE_LANGUAGES: frozenset[str] = frozenset(
    {
        "en",
        "hi",
        "gu",
        "bn",
        "ta",
        "te",
        "mr",
        "ja",
        "ko",
        "zh",
        "fr",
        "es",
        "pt",
        "de",
        "ar",
    }
)

_NAME_TO_CODE: dict[str, str] = {
    "english": "en",
    "en": "en",
    "hindi": "hi",
    "hi": "hi",
    "gujarati": "gu",
    "gu": "gu",
    "bengali": "bn",
    "bangla": "bn",
    "bn": "bn",
    "tamil": "ta",
    "ta": "ta",
    "telugu": "te",
    "te": "te",
    "marathi": "mr",
    "mr": "mr",
    "japanese": "ja",
    "ja": "ja",
    "korean": "ko",
    "ko": "ko",
    "chinese": "zh",
    "mandarin": "zh",
    "zh": "zh",
    "zh-cn": "zh",
    "zh_cn": "zh",
    "french": "fr",
    "fr": "fr",
    "spanish": "es",
    "es": "es",
    "portuguese": "pt",
    "pt": "pt",
    "german": "de",
    "de": "de",
    "arabic": "ar",
    "ar": "ar",
}

_DEFAULT_ENGLISH = "en-US-JennyNeural"


def _norm(value: str) -> str:
    return " ".join((value or "").strip().lower().replace("_", " ").replace("-", " ").split())


@lru_cache(maxsize=1)
def _load_locales() -> dict[str, Any]:
    return json.loads(_LOCALES_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _load_accents() -> dict[str, str]:
    raw = json.loads(_ACCENTS_PATH.read_text(encoding="utf-8"))
    return {str(k).lower(): str(v) for k, v in raw.items()}


def clear_locale_cache() -> None:
    _load_locales.cache_clear()
    _load_accents.cache_clear()


def normalize_language(name_or_code: str) -> str:
    """Return ISO-ish language code; unknown → en."""
    key = _norm(name_or_code).replace(" ", "")
    # also try with spaces removed from multi-word
    spaced = _norm(name_or_code)
    if key in _NAME_TO_CODE:
        return _NAME_TO_CODE[key]
    if spaced in _NAME_TO_CODE:
        return _NAME_TO_CODE[spaced]
    # bare code like "zh-CN"
    if "-" in (name_or_code or ""):
        base = (name_or_code or "").split("-", 1)[0].strip().lower()
        if base in SUPPORTED_VOICE_LANGUAGES:
            return base
    if key in SUPPORTED_VOICE_LANGUAGES:
        return key
    return "en"


def language_display_name(code: str) -> str:
    mapping = {
        "en": "English",
        "hi": "Hindi",
        "gu": "Gujarati",
        "bn": "Bengali",
        "ta": "Tamil",
        "te": "Telugu",
        "mr": "Marathi",
        "ja": "Japanese",
        "ko": "Korean",
        "zh": "Chinese",
        "fr": "French",
        "es": "Spanish",
        "pt": "Portuguese",
        "de": "German",
        "ar": "Arabic",
    }
    return mapping.get(normalize_language(code), code or "English")


def _normalize_gender(gender: str | None) -> str:
    g = (gender or "neutral").strip().lower()
    if g in {"male", "m", "man"}:
        return "male"
    if g in {"female", "f", "woman"}:
        return "female"
    return "neutral"


def resolve_accent_voice(language: str, country: str | None) -> str | None:
    code = normalize_language(language)
    country_key = _norm(country or "")
    if not country_key:
        return None
    accents = _load_accents()
    for key in (f"{code}|{country_key}",):
        if key in accents:
            return accents[key]
    # Also try country id-style without spaces
    compact = country_key.replace(" ", "")
    for k, v in accents.items():
        if not k.startswith(f"{code}|"):
            continue
        suffix = k.split("|", 1)[1]
        if suffix == country_key or suffix.replace(" ", "") == compact:
            return v
    return None


def resolve_edge_voice(
    language: str,
    gender: str | None = "neutral",
    country: str | None = None,
) -> str:
    """Resolve order: country accent → language+gender → English fallback."""
    accent = resolve_accent_voice(language, country)
    if accent:
        return accent
    code = normalize_language(language)
    g = _normalize_gender(gender)
    locales = _load_locales()
    entry = locales.get(code) or locales.get("en") or {}
    if isinstance(entry, dict):
        voice = entry.get(g) or entry.get("neutral") or entry.get("female")
        if voice:
            return str(voice)
    return _DEFAULT_ENGLISH
