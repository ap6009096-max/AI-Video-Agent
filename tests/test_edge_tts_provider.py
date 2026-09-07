"""Tests for EdgeTTSProvider with mocked edge_tts."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from config.settings import get_settings
from schemas.av_plan import VoicePlan
from tools.voice.provider import (
    EdgeTTSProvider,
    PassthroughTTSProvider,
    get_tts_provider,
)


def test_passthrough_when_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TTS_PROVIDER", "none")
    get_settings.cache_clear()
    provider = get_tts_provider()
    assert isinstance(provider, PassthroughTTSProvider)
    assert (
        provider.synthesize("hi", voice_plan=VoicePlan(), out_path=Path("x.mp3"))
        is None
    )
    get_settings.cache_clear()


def test_edge_provider_selected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TTS_PROVIDER", "edge")
    get_settings.cache_clear()

    class _FakeEdge:
        pass

    monkeypatch.setitem(__import__("sys").modules, "edge_tts", _FakeEdge())
    # Force EdgeTTSProvider.is_available True via import already set
    provider = get_tts_provider()
    assert provider.name == "edge"
    get_settings.cache_clear()


def test_edge_synthesize_writes_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "voice.mp3"

    class FakeCommunicate:
        def __init__(self, *args, **kwargs):
            self.kwargs = kwargs

        async def save(self, path: str) -> None:
            Path(path).write_bytes(b"ID3fake")

    fake_mod = MagicMock()
    fake_mod.Communicate = FakeCommunicate
    monkeypatch.setitem(__import__("sys").modules, "edge_tts", fake_mod)

    provider = EdgeTTSProvider()
    plan = VoicePlan(
        provider_voice_id="hi-IN-SwaraNeural",
        rate="+10%",
        pitch_ssml="+20Hz",
        volume="+0%",
    )
    result = provider.synthesize("नमस्ते", voice_plan=plan, out_path=out)
    assert result is not None
    assert result.is_file()
    assert result.read_bytes().startswith(b"ID3")
