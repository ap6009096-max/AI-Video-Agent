"""Tests for MusicAgent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.music_agent import MusicAgent
from config.settings import get_settings
from schemas.job import FeatureFlags, SourceType, VideoJobConfig
from schemas.project import ProjectMetadata


def test_music_agent_writes_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "mu1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="mu1", source_type=SourceType.SCRIPT, raw_text="x"
    )
    result = MusicAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(music="Cinematic"),
        features=FeatureFlags(music=True),
    )
    path = Path(result.music_path)
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["preset"]["name"] == "Cinematic"
    assert data["plan"]["generation_required"] is False
    assert data["plan"]["asset_path"] == ""
    get_settings.cache_clear()


def test_music_agent_all_moods_generation_false(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    moods = [
        "Original Audio",
        "No Music",
        "Background Music",
        "Dramatic",
        "Funny",
        "Energetic",
        "Emotional",
        "Educational",
    ]
    for i, mood in enumerate(moods):
        project_dir = tmp_path / "outputs" / "projects" / f"mu{i}"
        project_dir.mkdir(parents=True)
        project = ProjectMetadata(
            project_id=f"mu{i}", source_type=SourceType.SCRIPT, raw_text="x"
        )
        result = MusicAgent().run(
            project,
            project_dir=project_dir,
            config=VideoJobConfig(music=mood),
            features=FeatureFlags(music=True),
        )
        assert result.music_pack.plan.generation_required is False
        assert result.music_pack.preset.generation_required is False
    get_settings.cache_clear()


def test_music_agent_flag_off_skips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "mu_off"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="mu_off", source_type=SourceType.SCRIPT, raw_text="x"
    )
    result = MusicAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(music="Dramatic"),
        features=FeatureFlags(music=False),
    )
    assert result.music_pack.plan.skipped is True
    assert result.music_pack.plan.generation_required is False
    get_settings.cache_clear()
