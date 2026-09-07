"""Tests for DocumentaryAgent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.documentary_agent import DocumentaryAgent
from config.settings import get_settings
from schemas.documentary import DocumentaryChapter, GeminiDocumentaryBatch
from schemas.job import FeatureFlags, SourceType, VideoJobConfig
from schemas.project import ProjectMetadata
from tools.documentary.catalog import clear_documentary_cache


def test_documentary_flag_off_skips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    clear_documentary_cache()
    project_dir = tmp_path / "outputs" / "projects" / "doc1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="doc1", source_type=SourceType.SCRIPT, raw_text="x"
    )
    result = DocumentaryAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(platform="YouTube"),
        features=FeatureFlags(documentary=False),
    )
    assert result.documentary_pack.plan.skipped is True
    path = Path(result.documentary_path)
    assert path.name == "documentary_plan.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["plan"]["skipped"] is True
    get_settings.cache_clear()


def test_documentary_writes_public_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    clear_documentary_cache()
    project_dir = tmp_path / "outputs" / "projects" / "doc2"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="doc2", source_type=SourceType.SCRIPT, raw_text="x"
    )

    def _fake(**_: object) -> GeminiDocumentaryBatch:
        return GeminiDocumentaryBatch(
            introduction="Open on the mystery.",
            chapters=[
                DocumentaryChapter(title="Act One", summary="Setup"),
                DocumentaryChapter(title="Act Two", summary="Conflict"),
            ],
            conclusion="Leave with the lesson.",
        )

    result = DocumentaryAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(platform="YouTube"),
        features=FeatureFlags(documentary=True),
        script_pack={"primary": {"title": "River", "hook": "Listen"}},
        analyze_fn=_fake,
    )
    public = result.public_output()
    assert set(public.keys()) == {"introduction", "chapters", "conclusion"}
    assert public["introduction"] == "Open on the mystery."
    assert public["conclusion"] == "Leave with the lesson."
    assert len(public["chapters"]) == 2
    assert set(public["chapters"][0].keys()) == {"title", "summary"}
    assert Path(result.documentary_path).name == "documentary_plan.json"
    get_settings.cache_clear()
