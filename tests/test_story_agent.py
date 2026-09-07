"""Tests for StoryAgent with mocked Gemini generation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.story_agent import StoryAgent
from config.settings import get_settings
from schemas.clips import ClipCandidate, ClipsReport
from schemas.job import SourceType, VideoJobConfig
from schemas.project import ProjectMetadata
from schemas.story import GeminiClipStory, GeminiStoriesBatch


def _fake_stories(clip_blocks, **_kwargs) -> GeminiStoriesBatch:
    assert clip_blocks
    return GeminiStoriesBatch(
        stories=[
            GeminiClipStory(
                clip_id=0,
                hook="Attention: the key insight starts here",
                context="Viewers need a brief setup",
                value_event="The core tip from the source",
                payoff="Why it matters in practice",
                cta="Follow for more tips",
            )
        ]
    )


def test_story_agent_writes_stories_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "s1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="s1", source_type=SourceType.SCRIPT, raw_text="x"
    )
    clips = ClipsReport(
        project_id="s1",
        clips=[
            ClipCandidate(
                id=0,
                start=0.0,
                end=20.0,
                duration=20.0,
                transcript="The key insight starts here with a practical tip.",
                category="important",
                score=0.9,
                hook="The key insight",
                reason="seed",
                title="Insight",
                evidence=["seed:moments"],
            )
        ],
    )

    result = StoryAgent(generate_fn=_fake_stories).run(
        project,
        project_dir=project_dir,
        clips=clips,
        config=VideoJobConfig(video_type="Short-form"),
    )
    path = Path(result.stories_path)
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    story = data["stories"][0]
    assert story["structure"]["hook"]
    assert story["structure"]["context"]
    assert story["structure"]["value_event"]
    assert story["structure"]["payoff"]
    assert story["structure"]["cta"]
    assert "key insight" in story["source_excerpt"].lower()
    get_settings.cache_clear()


def test_story_agent_empty_clips_skips_gemini(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "s2"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="s2", source_type=SourceType.SCRIPT, raw_text="x"
    )

    def _should_not_run(*_a, **_k):
        raise AssertionError("Gemini should not be called for empty clips")

    result = StoryAgent(generate_fn=_should_not_run).run(
        project,
        project_dir=project_dir,
        clips=ClipsReport(project_id="s2", clips=[]),
    )
    assert result.stories.stories == []
    assert result.stories.provider == "skipped"
    assert Path(result.stories_path).is_file()
    get_settings.cache_clear()
