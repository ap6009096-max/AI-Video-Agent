"""Tests for MomentDetectionAgent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.moment_detection_agent import MomentDetectionAgent
from config.settings import get_settings
from schemas.job import FeatureFlags, SourceType
from schemas.moments import DetectedMoment
from schemas.project import ProjectMetadata


def test_agent_writes_moments_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "m1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(project_id="m1", source_type=SourceType.SCRIPT, raw_text="x")

    def _fake(**_kwargs):
        return [
            DetectedMoment(
                id=0,
                category="funny",
                start=0.0,
                end=2.0,
                title="Joke",
                reason="laughter",
                score=0.8,
                transcript="haha",
                evidence=["audio:laughter@0.0"],
            )
        ]

    result = MomentDetectionAgent(analyze_fn=_fake).run(
        project,
        project_dir=project_dir,
        features=FeatureFlags(funny_moments=True, viral_moments=False),
    )
    path = Path(result.moments_path)
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["moments"][0]["category"] == "funny"
    assert data["moments"][0]["evidence"]
    assert "score" in data["moments"][0]
    get_settings.cache_clear()


def test_smart_clip_off_writes_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "m2"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(project_id="m2", source_type=SourceType.SCRIPT, raw_text="x")
    result = MomentDetectionAgent().run(
        project,
        project_dir=project_dir,
        features=FeatureFlags(smart_clip_detection=False, funny_moments=True),
    )
    assert result.moments.moments == []
    assert result.moments.provider == "disabled"
    assert Path(result.moments_path).is_file()
    get_settings.cache_clear()


def test_only_funny_filters_categories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "m3"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(project_id="m3", source_type=SourceType.SCRIPT, raw_text="x")

    def _fake(*, enabled, **_):
        # Registry would filter; simulate returning only enabled
        assert enabled == ["funny"]
        return [
            DetectedMoment(
                category="funny",
                start=0.0,
                end=1.0,
                title="f",
                reason="r",
                score=0.7,
                transcript="lol",
                evidence=["e"],
            )
        ]

    result = MomentDetectionAgent(analyze_fn=_fake).run(
        project,
        project_dir=project_dir,
        features=FeatureFlags(
            funny_moments=True,
            viral_moments=False,
            important_moments=False,
            emotional_moments=False,
            educational_moments=False,
            surprise_moments=False,
            reaction_moments=False,
            inspirational_moments=False,
            cinematic_moments=False,
            expert_insights=False,
            best_quotes=False,
        ),
    )
    assert all(m.category == "funny" for m in result.moments.moments)
    get_settings.cache_clear()


def test_agent_passes_funny_moments_to_analyze(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "m4"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(project_id="m4", source_type=SourceType.SCRIPT, raw_text="x")
    funny_report = {
        "moments": [
            {
                "start": 0.0,
                "end": 1.5,
                "category": "funny",
                "humor_kinds": ["sarcasm"],
                "humor_score": 0.55,
                "explanation": "from funny agent",
                "transcript": "yeah right",
                "suggested_title": "Sarcasm",
                "evidence": ["e"],
            }
        ]
    }
    seen: dict = {}

    def _fake(*, enabled, funny_moments=None, **_):
        seen["funny_moments"] = funny_moments
        return [
            DetectedMoment(
                category="funny",
                start=0.0,
                end=1.5,
                title="Sarcasm",
                reason="from funny agent",
                score=0.55,
                transcript="yeah right",
                evidence=["e"],
            )
        ]

    result = MomentDetectionAgent(analyze_fn=_fake).run(
        project,
        project_dir=project_dir,
        features=FeatureFlags(funny_moments=True),
        funny_moments=funny_report,
    )
    assert seen["funny_moments"] is funny_report
    assert result.moments.moments[0].title == "Sarcasm"
    get_settings.cache_clear()


def test_agent_passes_viral_moments_to_analyze(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "m5"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(project_id="m5", source_type=SourceType.SCRIPT, raw_text="x")
    viral_report = {
        "moments": [
            {
                "start": 0.0,
                "end": 2.0,
                "category": "viral",
                "final_score": 0.7,
                "rank": 1,
                "explanation": "heuristic",
                "transcript": "wow",
                "suggested_title": "Viral hit",
                "evidence": ["e"],
                "scores": {
                    "hook": 0.8,
                    "information": 0.5,
                    "emotion": 0.7,
                    "humor": 0.2,
                    "visual": 0.4,
                    "completeness": 0.6,
                    "shareability": 0.5,
                    "reasons": {},
                },
            }
        ]
    }
    seen: dict = {}

    def _fake(*, enabled, viral_moments=None, **_):
        seen["viral_moments"] = viral_moments
        return [
            DetectedMoment(
                category="viral",
                start=0.0,
                end=2.0,
                title="Viral hit",
                reason="heuristic",
                score=0.7,
                transcript="wow",
                evidence=["e"],
            )
        ]

    result = MomentDetectionAgent(analyze_fn=_fake).run(
        project,
        project_dir=project_dir,
        features=FeatureFlags(viral_moments=True),
        viral_moments=viral_report,
    )
    assert seen["viral_moments"] is viral_report
    assert result.moments.moments[0].title == "Viral hit"
    get_settings.cache_clear()
