"""Tests for ResearchAgent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.research_agent import ResearchAgent
from config.settings import get_settings
from schemas.job import FeatureFlags, SourceType, VideoJobConfig
from schemas.project import ProjectMetadata
from schemas.research import ResearchClaim, ResearchOutlineSection, ResearchReport, ResearchSource, TopicAnalysis


def test_agent_writes_research_report_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "r1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="r1",
        source_type=SourceType.UPLOAD,
        source_path="clip.mp4",
        raw_text="",
    )

    def _fake(**_kwargs):
        return ResearchReport(
            project_id="r1",
            topic="Water",
            topic_analysis=TopicAnalysis(primary_topic="Water"),
            sources=[
                ResearchSource(
                    id="src:user_script",
                    kind="user_script",
                    title="Script",
                    excerpt="Water boils at 100C.",
                )
            ],
            claims=[
                ResearchClaim(
                    id="claim:0",
                    text="Water boils at 100C.",
                    source_ids=["src:user_script"],
                    confidence=0.9,
                )
            ],
            outline=[
                ResearchOutlineSection(
                    id="outline:0",
                    title="Basics",
                    summary="Boiling point",
                    claim_ids=["claim:0"],
                )
            ],
            summary="Water boils at 100C.",
            provider="test",
        )

    result = ResearchAgent(build_fn=_fake).run(
        project,
        project_dir=project_dir,
        features=FeatureFlags(research=True),
        config=VideoJobConfig(),
    )
    path = Path(result.research_report_path)
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["claims"][0]["source_ids"] == ["src:user_script"]
    assert data["topic"] == "Water"
    get_settings.cache_clear()


def test_script_source_enables_without_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "r2"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="r2",
        source_type=SourceType.SCRIPT,
        raw_text="Photosynthesis converts light into chemical energy.",
    )

    def _fake(**kwargs):
        assert kwargs.get("skipped") is not True
        return ResearchReport(
            project_id="r2",
            topic="Photosynthesis",
            sources=[
                ResearchSource(
                    id="src:user_script",
                    kind="user_script",
                    title="User script",
                    excerpt="Photosynthesis converts light into chemical energy.",
                )
            ],
            claims=[
                ResearchClaim(
                    id="claim:0",
                    text="Photosynthesis converts light into chemical energy.",
                    source_ids=["src:user_script"],
                    confidence=0.8,
                )
            ],
            outline=[
                ResearchOutlineSection(
                    id="outline:0",
                    title="Core",
                    claim_ids=["claim:0"],
                )
            ],
            summary="Photosynthesis converts light into chemical energy.",
        )

    result = ResearchAgent(build_fn=_fake).run(
        project,
        project_dir=project_dir,
        features=FeatureFlags(research=False),
        config=VideoJobConfig(),
    )
    assert result.research_report.claims
    assert result.research_report.skipped is False
    get_settings.cache_clear()


def test_disabled_writes_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "r3"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="r3",
        source_type=SourceType.UPLOAD,
        source_path="x.mp4",
    )
    result = ResearchAgent().run(
        project,
        project_dir=project_dir,
        features=FeatureFlags(research=False),
        config=VideoJobConfig(),
        source_type=SourceType.UPLOAD,
    )
    assert result.research_report.skipped is True
    assert result.research_report.claims == []
    assert Path(result.research_report_path).is_file()
    get_settings.cache_clear()
