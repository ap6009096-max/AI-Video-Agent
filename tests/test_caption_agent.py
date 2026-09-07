"""Tests for CaptionAgent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.caption_agent import CaptionAgent
from config.settings import get_settings
from schemas.job import FeatureFlags, SourceType, VideoJobConfig
from schemas.project import ProjectMetadata


SPEECH = {
    "language": "en",
    "media_path": "",
    "segments": [
        {
            "id": 0,
            "start": 0.0,
            "end": 2.0,
            "text": "Hello viral world",
            "words": [
                {"word": "Hello", "start": 0.0, "end": 0.5},
                {"word": "viral", "start": 0.5, "end": 1.2},
                {"word": "world", "start": 1.2, "end": 2.0},
            ],
        }
    ],
}


def test_caption_agent_writes_exports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "cap1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="cap1", source_type=SourceType.UPLOAD, source_path=""
    )
    result = CaptionAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(
            caption_style="Kinetic",
            caption_emoji=False,
            caption_burn_in=True,
            platform="TikTok",
        ),
        features=FeatureFlags(captions=True),
        speech_transcript=SPEECH,
    )
    path = Path(result.captions_path)
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["plan"]["timed"] is True
    assert data["plan"]["burn_in_applied"] is False  # no media / soft-skip
    assert data["srt_path"]
    assert Path(data["srt_path"]).is_file()
    assert Path(data["vtt_path"]).is_file()
    assert data["ass_path"]  # Kinetic animation → ASS
    assert Path(data["ass_path"]).is_file()
    assert data["burned_in_path"] == ""
    assert data["word_cues"]
    assert data["sentence_cues"]
    get_settings.cache_clear()


def test_caption_agent_tiktok_writes_ass_with_karaoke(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    from tools.captions.catalog import clear_caption_cache

    clear_caption_cache()
    project_dir = tmp_path / "outputs" / "projects" / "cap_tt"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="cap_tt", source_type=SourceType.UPLOAD, source_path=""
    )
    result = CaptionAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(
            caption_style="TikTok",
            caption_emoji=True,
            caption_burn_in=False,
            platform="TikTok",
        ),
        features=FeatureFlags(captions=True),
        speech_transcript=SPEECH,
    )
    data = json.loads(Path(result.captions_path).read_text(encoding="utf-8"))
    assert data["ass_path"]
    ass_text = Path(data["ass_path"]).read_text(encoding="utf-8")
    assert "\\k" in ass_text
    assert "\\t(" in ass_text
    # Sentence cues should carry words for karaoke
    assert any(c.get("words") for c in data["sentence_cues"])
    get_settings.cache_clear()


def test_caption_agent_flag_off_skips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "cap2"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="cap2", source_type=SourceType.SCRIPT, raw_text="x"
    )
    result = CaptionAgent().run(
        project,
        project_dir=project_dir,
        features=FeatureFlags(captions=False),
        speech_transcript=SPEECH,
    )
    assert result.captions_pack.plan.skipped is True
    assert result.captions_pack.srt_path == ""
    get_settings.cache_clear()


def test_caption_agent_no_timestamps_no_exports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "cap3"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="cap3", source_type=SourceType.SCRIPT, raw_text="hello"
    )
    result = CaptionAgent().run(
        project,
        project_dir=project_dir,
        features=FeatureFlags(captions=True),
        transcript={
            "sentences": [{"text": "hello", "start_seconds": None, "end_seconds": None}]
        },
    )
    assert result.captions_pack.plan.timed is False
    assert result.captions_pack.srt_path == ""
    assert result.captions_pack.burned_in_path == ""
    assert not (project_dir / "captions" / "captions.srt").exists()
    get_settings.cache_clear()
