"""Tests for voice catalog and TTS passthrough behavior."""

from __future__ import annotations

from config.settings import get_settings
from tools.voice.catalog import build_voice_pack, list_voices, resolve_voice
from tools.voice.provider import PassthroughTTSProvider, get_tts_provider


REQUIRED_VOICES = [
    "Original Voice",
    "AI Voice",
    "Male",
    "Female",
    "Neutral",
]


def test_catalog_loads_voices() -> None:
    voices = list_voices()
    names = {v.name for v in voices}
    missing = [n for n in REQUIRED_VOICES if n not in names]
    assert not missing, f"Missing voices: {missing}"


def test_resolve_original_and_ai() -> None:
    original = resolve_voice("Original Voice")
    assert original is not None
    assert original.mode == "original"
    ai = resolve_voice("AI Voice")
    assert ai is not None
    assert ai.mode == "ai_tts"


def test_original_voice_preserves() -> None:
    pack = build_voice_pack("Original Voice", enabled=True)
    assert pack.plan.preserve_original is True
    assert pack.plan.audio_path == ""


def test_ai_voice_without_provider_preserves(monkeypatch) -> None:
    monkeypatch.setattr("tools.voice.catalog.get_tts_provider", lambda: PassthroughTTSProvider())
    pack = build_voice_pack("AI Voice", enabled=True)
    assert pack.plan.preserve_original is True
    assert pack.plan.provider == "passthrough"
    assert pack.plan.provider_ready is False
    assert pack.plan.audio_path == ""


def test_passthrough_provider_no_audio(monkeypatch) -> None:
    monkeypatch.setenv("TTS_PROVIDER", "none")
    get_settings.cache_clear()
    provider = get_tts_provider()
    assert isinstance(provider, PassthroughTTSProvider)
    assert provider.is_available()
    from pathlib import Path
    from schemas.av_plan import VoicePlan

    out = provider.synthesize(
        "hello",
        voice_plan=VoicePlan(),
        out_path=Path("unused.wav"),
    )
    assert out is None
    get_settings.cache_clear()

