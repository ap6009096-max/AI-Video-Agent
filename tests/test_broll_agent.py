"""Tests for BRollAgent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.broll_agent import BRollAgent
from config.settings import get_settings
from schemas.job import FeatureFlags, SourceType, VideoJobConfig
from schemas.project import ProjectMetadata
from tools.broll.catalog import VALID_SOURCE_KINDS


def test_broll_agent_writes_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "br1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="br1", source_type=SourceType.SCRIPT, raw_text="x"
    )
    result = BRollAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(),
        features=FeatureFlags(b_roll=True),
        clips={"clips": [{"id": 1, "start": 0.0, "end": 3.0}]},
        environment_pack={
            "plan": {"broll_requirements": "Misty canopy establishing"},
            "preset": {},
        },
    )
    path = Path(result.broll_path)
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["plan"]["skipped"] is False
    assert data["plan"]["items"]
    for item in data["plan"]["items"]:
        assert item["source_kind"] in VALID_SOURCE_KINDS
        if item["available"]:
            assert (item.get("asset_path") or "").strip()
        else:
            assert item["available"] is False
    get_settings.cache_clear()


def test_broll_agent_skipped_when_flag_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "br2"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="br2", source_type=SourceType.SCRIPT, raw_text="x"
    )
    result = BRollAgent().run(
        project,
        project_dir=project_dir,
        features=FeatureFlags(b_roll=False),
        clips={"clips": [{"id": 1}]},
    )
    assert result.broll_pack.plan.skipped is True
    assert result.broll_pack.plan.items == []
    assert Path(result.broll_path).is_file()
    get_settings.cache_clear()


def test_broll_agent_never_available_without_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "br3"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="br3", source_type=SourceType.SCRIPT, raw_text="x"
    )
    result = BRollAgent().run(
        project,
        project_dir=project_dir,
        features=FeatureFlags(b_roll=True),
        clips={"clips": [{"id": 2, "start": 0, "end": 1}]},
    )
    for item in result.broll_pack.plan.items:
        assert not (item.available and not (item.asset_path or "").strip())
    get_settings.cache_clear()
