"""Tests for ExportAgent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.export_agent import ExportAgent
from config.settings import get_settings
from core.errors import ExportAgentError
from schemas.job import SourceType
from schemas.project import ProjectMetadata


def test_export_agent_manifest_soft_skip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "ex1"
    (project_dir / "exports").mkdir(parents=True)
    (project_dir / "exports" / "platform_metadata.json").write_text(
        "{}", encoding="utf-8"
    )
    project = ProjectMetadata(
        project_id="ex1", source_type=SourceType.SCRIPT, raw_text="x"
    )
    result = ExportAgent().run(
        project,
        project_dir=project_dir,
        render_pack={"plan": {"skipped": True, "encoded": False}},
        quality_pack={"report": {"passed": True, "skipped": True}},
        platform_pack={"export_path": str(project_dir / "exports" / "platform_metadata.json")},
    )
    manifest = Path(result.export_manifest_path)
    assert manifest.is_file()
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["skipped"] is True
    assert result.export_pack.export_path.endswith("manifest.json")
    get_settings.cache_clear()


def test_export_refuses_failed_quality(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "ex2"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="ex2", source_type=SourceType.UPLOAD, source_path=""
    )
    with pytest.raises(ExportAgentError):
        ExportAgent().run(
            project,
            project_dir=project_dir,
            quality_pack={"report": {"passed": False, "skipped": False}},
            render_pack={"plan": {"encoded": True, "output_path": "x.mp4"}},
        )
    get_settings.cache_clear()
