"""Tests for AvatarAgent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.avatar_agent import AvatarAgent
from config.settings import get_settings
from schemas.job import FeatureFlags, SourceType, VideoJobConfig
from schemas.project import ProjectMetadata


def test_avatar_flag_off_skips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "av1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="av1", source_type=SourceType.SCRIPT, raw_text="x"
    )
    result = AvatarAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(avatar="Male presenter"),
        features=FeatureFlags(avatar=False),
    )
    assert result.avatar_pack.plan.skipped is True
    data = json.loads(Path(result.avatar_path).read_text(encoding="utf-8"))
    assert data["plan"]["skipped"] is True
    get_settings.cache_clear()


def test_avatar_writes_public_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "av2"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="av2", source_type=SourceType.SCRIPT, raw_text="x"
    )
    voice_pack = {
        "preset": {"name": "Hindi Female"},
        "plan": {
            "preset_name": "Hindi Female",
            "emotion": "happy",
            "language_hint": "Hindi",
            "language_code": "hi",
            "primary_audio_path": str(project_dir / "audio" / "voice_hi.mp3"),
        },
    }
    locale_pack = {
        "language": {"name": "Hindi", "code": "hi"},
        "country": {"name": "India"},
    }
    result = AvatarAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(
            avatar="News anchor",
            language="Hindi",
            voice="Hindi Female",
            voice_emotion="happy",
        ),
        features=FeatureFlags(avatar=True),
        voice_pack=voice_pack,
        locale_pack=locale_pack,
    )
    plan = result.avatar_pack.plan
    assert plan.skipped is False
    assert plan.avatar_type == "News anchor"
    assert plan.voice == "Hindi Female"
    assert plan.language == "Hindi"
    assert plan.emotion == "happy"
    assert plan.speaking_language_code == "hi"
    assert plan.lip_sync is True
    public = result.public_output()
    assert set(public.keys()) == {"avatar_type", "voice", "language", "emotion"}
    get_settings.cache_clear()
