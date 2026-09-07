"""Tests for PlatformAgent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.platform_agent import PlatformAgent
from config.settings import get_settings
from schemas.job import FeatureFlags, SourceType, VideoJobConfig
from schemas.project import ProjectMetadata


def test_platform_agent_writes_plan_and_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "plat1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="plat1", source_type=SourceType.SCRIPT, raw_text="x"
    )
    result = PlatformAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(platform="TikTok"),
        features=FeatureFlags(platform_optimization=True),
        scripts={
            "scripts": [
                {
                    "title": "Fast tip",
                    "hook": "Watch this",
                    "caption": "Caption text",
                    "cta": "Follow",
                    "keywords": ["tip"],
                }
            ]
        },
    )
    path = Path(result.platform_path)
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["plan"]["skipped"] is False
    assert data["preset"]["publish_enabled"] is False
    assert data["plan"]["export_hints"]["publish_status"] == "not_published"
    assert data["export_path"]
    export = Path(data["export_path"])
    assert export.is_file()
    export_data = json.loads(export.read_text(encoding="utf-8"))
    assert export_data["publish_enabled"] is False
    assert "not publishing" in export_data["notes"].lower()
    get_settings.cache_clear()


def test_platform_agent_flag_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "plat2"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="plat2", source_type=SourceType.SCRIPT, raw_text="x"
    )
    result = PlatformAgent().run(
        project,
        project_dir=project_dir,
        features=FeatureFlags(platform_optimization=False),
    )
    assert result.platform_pack.plan.skipped is True
    assert result.platform_pack.export_path == ""
    assert not (project_dir / "exports" / "platform_metadata.json").exists()
    get_settings.cache_clear()
