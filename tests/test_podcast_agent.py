"""Tests for PodcastAgent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.podcast_agent import PodcastAgent
from config.settings import get_settings
from schemas.job import FeatureFlags, SourceType, VideoJobConfig
from schemas.podcast import PodcastClip
from schemas.project import ProjectMetadata


def test_agent_writes_podcast_clips_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "p1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="p1", source_type=SourceType.UPLOAD, source_path="ep.mp3"
    )

    def _fake(**_kwargs):
        return [
            PodcastClip(
                id=0,
                start=0.0,
                end=40.0,
                duration=40.0,
                kind="quote",
                platforms=["quotes", "shorts"],
                transcript="A sharp claim.",
                title="Sharp claim",
                hook="A sharp claim",
                reason="quote package",
                score=0.8,
                evidence=["seed:quote"],
            )
        ]

    result = PodcastAgent(package_fn=_fake).run(
        project,
        project_dir=project_dir,
        features=FeatureFlags(podcast_clips=True),
        config=VideoJobConfig(video_type="Shorts"),
        upload_path="ep.mp3",
    )
    path = Path(result.podcast_clips_path)
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["clips"][0]["kind"] == "quote"
    assert "shorts" in data["clips"][0]["platforms"]
    assert data["source_media"] == "audio"
    get_settings.cache_clear()


def test_video_type_podcast_enables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "p2"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(project_id="p2", source_type=SourceType.SCRIPT, raw_text="x")

    def _fake(**_kwargs):
        return [
            PodcastClip(
                start=1.0,
                end=20.0,
                duration=19.0,
                kind="lesson",
                platforms=["shorts", "highlights"],
                transcript="Learn this.",
                title="Lesson",
                hook="Learn this",
                reason="lesson",
                score=0.7,
            )
        ]

    result = PodcastAgent(package_fn=_fake).run(
        project,
        project_dir=project_dir,
        features=FeatureFlags(podcast_clips=False),
        config=VideoJobConfig(video_type="Podcast"),
    )
    assert result.podcast_clips.provider == "podcast-packager"
    assert result.podcast_clips.clips
    get_settings.cache_clear()


def test_disabled_writes_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "p3"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(project_id="p3", source_type=SourceType.SCRIPT, raw_text="x")
    result = PodcastAgent().run(
        project,
        project_dir=project_dir,
        features=FeatureFlags(podcast_clips=False),
        config=VideoJobConfig(video_type="Shorts"),
    )
    assert result.podcast_clips.clips == []
    assert result.podcast_clips.provider == "disabled"
    assert Path(result.podcast_clips_path).is_file()
    get_settings.cache_clear()
