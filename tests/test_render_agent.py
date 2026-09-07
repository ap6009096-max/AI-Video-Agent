"""Tests for RenderAgent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.render_agent import RenderAgent
from config.settings import get_settings
from schemas.job import SourceType, VideoJobConfig
from schemas.project import ProjectMetadata


def test_render_agent_plan_soft_skip_without_media(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "rd1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="rd1", source_type=SourceType.SCRIPT, raw_text="hello"
    )
    result = RenderAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(platform="TikTok", reframe_aspect="9:16"),
        platform_pack={
            "plan": {
                "metadata": {"aspect_recommendation": "9:16"},
                "export_hints": {"preferred_aspect": "9:16"},
            }
        },
    )
    path = Path(result.render_path)
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["plan"]["skipped"] is True
    assert data["plan"]["encoded"] is False
    assert data["plan"]["target_aspect"] == "9:16"
    get_settings.cache_clear()
