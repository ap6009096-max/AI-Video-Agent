"""Tests for multi-language voice locale / accent map."""

from __future__ import annotations

from tools.voice.locale_map import (
    SUPPORTED_VOICE_LANGUAGES,
    normalize_language,
    resolve_accent_voice,
    resolve_edge_voice,
)


def test_all_fifteen_languages_supported() -> None:
    assert len(SUPPORTED_VOICE_LANGUAGES) == 15
    for code in (
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
    ):
        assert code in SUPPORTED_VOICE_LANGUAGES
        voice = resolve_edge_voice(code, "female")
        assert voice and "Neural" in voice


def test_normalize_language_names() -> None:
    assert normalize_language("Hindi") == "hi"
    assert normalize_language("Bengali") == "bn"
    assert normalize_language("Telugu") == "te"
    assert normalize_language("Chinese") == "zh"
    assert normalize_language("zh-CN") == "zh"
    assert normalize_language("unknown-xyz") == "en"


def test_country_accent_overrides() -> None:
    uk = resolve_accent_voice("en", "United Kingdom")
    assert uk is not None and "GB" in uk
    india = resolve_accent_voice("en", "India")
    assert india is not None and "IN" in india
    mx = resolve_accent_voice("es", "Mexico")
    assert mx is not None and "MX" in mx

    assert resolve_edge_voice("English", "neutral", "United Kingdom") == uk
    assert resolve_edge_voice("Spanish", "female", "Mexico") == mx


def test_gender_selection() -> None:
    male = resolve_edge_voice("hi", "male")
    female = resolve_edge_voice("hi", "female")
    assert male != female
    assert "Madhur" in male or "hi-IN" in male
