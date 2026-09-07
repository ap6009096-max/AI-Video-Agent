"""Tests for CharacterAgent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.character_agent import CharacterAgent
from config.settings import get_settings
from schemas.character import CharacterProfile, GeminiCharacterBatch
from schemas.job import FeatureFlags, SourceType, VideoJobConfig
from schemas.project import ProjectMetadata
from tools.character.catalog import clear_character_cache


def test_character_flag_off_skips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    clear_character_cache()
    project_dir = tmp_path / "outputs" / "projects" / "ch1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="ch1", source_type=SourceType.SCRIPT, raw_text="x"
    )
    result = CharacterAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(platform="YouTube"),
        features=FeatureFlags(character=False),
    )
    assert result.character_pack.plan.skipped is True
    data = json.loads(Path(result.character_path).read_text(encoding="utf-8"))
    assert data["plan"]["skipped"] is True
    get_settings.cache_clear()


def test_character_writes_public_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    clear_character_cache()
    project_dir = tmp_path / "outputs" / "projects" / "ch2"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="ch2", source_type=SourceType.SCRIPT, raw_text="x"
    )

    def _fake(**_: object) -> GeminiCharacterBatch:
        return GeminiCharacterBatch(
            characters=[
                CharacterProfile(
                    name="Host",
                    role_type="human",
                    appearance="adult with short dark hair",
                    clothing="olive jacket",
                    voice="warm conversational",
                    personality="curious",
                    expressions=["smile", "concern"],
                )
            ],
            consistency_notes=["Keep Host clothing identical across scenes."],
        )

    result = CharacterAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(platform="YouTube"),
        features=FeatureFlags(character=True),
        script_pack={"primary": {"title": "Tips", "hook": "Start here"}},
        analyze_fn=_fake,
    )
    public = result.public_output()
    assert set(public.keys()) == {"characters", "consistency_notes"}
    assert public["characters"][0]["name"] == "Host"
    assert set(public["characters"][0].keys()) == {
        "name",
        "role_type",
        "appearance",
        "clothing",
        "voice",
        "personality",
        "expressions",
    }
    assert public["consistency_notes"]
    get_settings.cache_clear()
