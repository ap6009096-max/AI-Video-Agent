"""Tests for SmartClipAgent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.smart_clip_agent import SmartClipAgent
from config.settings import get_settings
from schemas.clips import ClipCandidate
from schemas.job import FeatureFlags, SourceType, VideoJobConfig
from schemas.project import ProjectMetadata


def test_agent_writes_clips_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "c1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(project_id="c1", source_type=SourceType.SCRIPT, raw_text="x")

    def _fake(**kwargs):
        assert kwargs.get("target_duration") == 45
        return [
            ClipCandidate(
                id=0,
                start=0.0,
                end=44.0,
                duration=44.0,
                transcript="A full clipped thought about the topic.",
                category="important",
                score=0.77,
                hook="A full clipped thought",
                reason="snapped; target=45s",
                title="A full clipped thought",
                evidence=["seed:moments"],
            )
        ]

    result = SmartClipAgent(select_fn=_fake).run(
        project,
        project_dir=project_dir,
        features=FeatureFlags(smart_clip_detection=True),
        config=VideoJobConfig(target_clip_duration=45),
    )
    path = Path(result.clips_path)
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["target_duration"] == 45.0
    clip = data["clips"][0]
    assert clip["score"] == 0.77
    assert clip["hook"]
    assert clip["reason"]
    assert clip["duration"] == 44.0
    assert "fixed" in data["notes"].lower() or "boundaries" in data["notes"].lower()
    get_settings.cache_clear()


def test_flag_off_writes_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "c2"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(project_id="c2", source_type=SourceType.SCRIPT, raw_text="x")
    result = SmartClipAgent().run(
        project,
        project_dir=project_dir,
        features=FeatureFlags(smart_clip_detection=False),
    )
    assert result.clips.clips == []
    assert result.clips.provider == "disabled"
    assert Path(result.clips_path).is_file()
    get_settings.cache_clear()


def test_multi_shorts_flag_off_keeps_single_duration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "c3"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(project_id="c3", source_type=SourceType.SCRIPT, raw_text="x")
    called: dict[str, object] = {}

    def _fake(**kwargs):
        called.update(kwargs)
        return [
            ClipCandidate(
                id=0,
                start=0.0,
                end=30.0,
                duration=30.0,
                transcript="Single path clip.",
                category="important",
                score=0.7,
                hook="Single",
                reason="single",
                title="Single",
                evidence=[],
            )
        ]

    result = SmartClipAgent(select_fn=_fake).run(
        project,
        project_dir=project_dir,
        features=FeatureFlags(
            smart_clip_detection=True, multi_shorts_export=False
        ),
        config=VideoJobConfig(
            target_clip_duration=30, short_durations=[10, 40, 90]
        ),
    )
    assert called.get("target_duration") == 30
    data = json.loads(Path(result.clips_path).read_text(encoding="utf-8"))
    assert data.get("multi_shorts") in (False, None)
    assert len(data["clips"]) == 1
    get_settings.cache_clear()


def test_multi_shorts_flag_on_uses_multi_select(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "c4"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(project_id="c4", source_type=SourceType.SCRIPT, raw_text="x")

    def _fake_multi(**kwargs):
        assert kwargs.get("short_durations") == [10, 40]
        return [
            ClipCandidate(
                id=0,
                start=0.0,
                end=10.0,
                duration=10.0,
                target_duration=10,
                transcript="Ten second short.",
                category="important",
                score=0.8,
                hook="Ten",
                reason="multi",
                title="Ten",
                evidence=["multi_duration"],
                source_signals=["moments", "multi_duration"],
            )
        ]

    result = SmartClipAgent(select_multi_fn=_fake_multi).run(
        project,
        project_dir=project_dir,
        features=FeatureFlags(
            smart_clip_detection=True, multi_shorts_export=True
        ),
        config=VideoJobConfig(short_durations=[10, 40]),
    )
    data = json.loads(Path(result.clips_path).read_text(encoding="utf-8"))
    assert data.get("multi_shorts") is True
    assert data["clips"][0]["target_duration"] == 10
    get_settings.cache_clear()
