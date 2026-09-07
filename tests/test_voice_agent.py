"""Tests for VoiceAgent multi-language synthesis."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.voice_agent import VoiceAgent
from config.settings import get_settings
from schemas.av_plan import VoicePlan
from schemas.job import FeatureFlags, SourceType, VideoJobConfig
from schemas.project import ProjectMetadata
from tools.voice.catalog import clear_voice_cache


class _FakeTTS:
    name = "edge"

    def is_available(self) -> bool:
        return True

    def synthesize(self, text, *, voice_plan: VoicePlan, out_path: Path):
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"ID3" + (text or "").encode("utf-8")[:20])
        return out_path


def test_voice_agent_original_preserves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("TTS_PROVIDER", "none")
    get_settings.cache_clear()
    clear_voice_cache()
    project_dir = tmp_path / "outputs" / "projects" / "vo1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="vo1", source_type=SourceType.SCRIPT, raw_text="x"
    )
    result = VoiceAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(voice="Original Voice"),
        features=FeatureFlags(voice=True),
    )
    path = Path(result.voice_path)
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["plan"]["preserve_original"] is True
    assert data["preset"]["name"] == "Original Voice"
    get_settings.cache_clear()


def test_voice_agent_ai_without_provider_preserves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("TTS_PROVIDER", "")
    get_settings.cache_clear()
    clear_voice_cache()
    project_dir = tmp_path / "outputs" / "projects" / "vo2"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="vo2", source_type=SourceType.SCRIPT, raw_text="x"
    )
    result = VoiceAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(voice="AI Voice", language="English"),
        features=FeatureFlags(voice=True),
    )
    assert result.voice_pack.plan.preserve_original is True
    assert result.voice_pack.plan.provider_ready is False
    assert result.voice_pack.plan.audio_path == ""
    get_settings.cache_clear()


def test_voice_agent_flag_off_preserves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    clear_voice_cache()
    project_dir = tmp_path / "outputs" / "projects" / "vo3"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="vo3", source_type=SourceType.SCRIPT, raw_text="x"
    )
    result = VoiceAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(voice="AI Voice"),
        features=FeatureFlags(voice=False),
    )
    assert result.voice_pack.plan.preserve_original is True
    get_settings.cache_clear()


def test_voice_agent_synthesizes_hindi_from_localizations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("TTS_PROVIDER", "edge")
    get_settings.cache_clear()
    clear_voice_cache()
    monkeypatch.setattr(
        "agents.voice_agent.get_tts_provider", lambda: _FakeTTS()
    )
    monkeypatch.setattr(
        "tools.voice.catalog.get_tts_provider", lambda: _FakeTTS()
    )

    project_dir = tmp_path / "outputs" / "projects" / "vo_hi"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="vo_hi", source_type=SourceType.SCRIPT, raw_text="x"
    )
    localizations = {
        "versions": [
            {
                "target": {"language": "Hindi"},
                "locale_pack": {
                    "language": {"name": "Hindi", "code": "hi"}
                },
                "scripts": [
                    {
                        "short_script": "नमस्ते दोस्तों यह एक टेस्ट है",
                        "hook": "नमस्ते",
                    }
                ],
            }
        ]
    }
    result = VoiceAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(
            voice="Hindi Female",
            language="Hindi",
            country="India",
            voice_emotion="happy",
            voice_speed=1.1,
            voice_pitch=1.0,
        ),
        features=FeatureFlags(voice=True),
        localizations=localizations,
        locale_pack={"language": {"name": "Hindi", "code": "hi"}, "country": {"name": "India"}},
    )
    assert result.voice_pack.plan.preserve_original is False
    assert result.voice_pack.plan.primary_audio_path
    audio = Path(result.voice_pack.plan.primary_audio_path)
    assert audio.is_file()
    assert "voice_hi" in audio.name
    assert result.voice_pack.plan.language_code == "hi"
    assert result.voice_pack.plan.emotion == "happy"
    assert any(t.ok for t in result.voice_pack.plan.tracks)
    get_settings.cache_clear()
