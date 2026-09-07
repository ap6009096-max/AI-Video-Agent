"""Tests for DirectorAgent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.director_agent import DirectorAgent
from config.settings import get_settings
from schemas.director import GeminiDirectorBatch
from schemas.job import FeatureFlags, SourceType, VideoJobConfig
from schemas.project import ProjectMetadata
from tools.director.catalog import clear_director_cache


def test_director_flag_off_skips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    clear_director_cache()
    project_dir = tmp_path / "outputs" / "projects" / "dir1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="dir1", source_type=SourceType.SCRIPT, raw_text="x"
    )
    result = DirectorAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(platform="YouTube"),
        features=FeatureFlags(director=False),
    )
    assert result.director_pack.plan.skipped is True
    data = json.loads(Path(result.director_path).read_text(encoding="utf-8"))
    assert data["plan"]["skipped"] is True
    get_settings.cache_clear()


def test_director_writes_public_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    clear_director_cache()
    project_dir = tmp_path / "outputs" / "projects" / "dir2"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="dir2", source_type=SourceType.SCRIPT, raw_text="x"
    )

    def _fake(**_: object) -> GeminiDirectorBatch:
        return GeminiDirectorBatch(
            scene_order=[1, 2],
            continuity_notes=["Story: Link beat 1 to 2.", "Camera: Hold axis."],
            camera_flow=["scene 1→2: establish wide then push in"],
        )

    result = DirectorAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(platform="YouTube"),
        features=FeatureFlags(director=True),
        script_pack={"primary": {"title": "Tips", "hook": "Start here"}},
        analyze_fn=_fake,
    )
    plan = result.director_pack.plan
    assert plan.skipped is False
    public = result.public_output()
    assert set(public.keys()) == {"scene_order", "continuity_notes", "camera_flow"}
    assert public["scene_order"] == [1, 2]
    assert public["continuity_notes"]
    assert public["camera_flow"]
    get_settings.cache_clear()
