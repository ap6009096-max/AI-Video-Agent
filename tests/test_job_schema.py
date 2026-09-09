"""Tests for video job request schemas."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from schemas.job import FeatureFlags, SourceType, VideoJobConfig, VideoJobRequest


def test_youtube_request_valid() -> None:
    req = VideoJobRequest(
        source_type=SourceType.YOUTUBE,
        youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    )
    assert req.source_type == SourceType.YOUTUBE
    assert req.features.smart_clip_detection is True
    assert req.features.captions is True
    assert req.features.funny_moments is False
    assert req.config.target_clip_duration == 30


def test_youtube_request_rejects_non_youtube() -> None:
    with pytest.raises(ValidationError):
        VideoJobRequest(
            source_type=SourceType.YOUTUBE,
            youtube_url="https://example.com/video",
        )


def test_upload_request_valid(tmp_path: Path) -> None:
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake")
    req = VideoJobRequest(
        source_type=SourceType.UPLOAD,
        upload_path=str(video),
    )
    assert req.upload_path.endswith(".mp4")


def test_audio_upload_extensions_accepted(tmp_path: Path) -> None:
    for ext in (".mp3", ".wav", ".m4a", ".flac"):
        audio = tmp_path / f"ep{ext}"
        audio.write_bytes(b"fake")
        req = VideoJobRequest(
            source_type=SourceType.UPLOAD,
            upload_path=str(audio),
        )
        assert req.upload_path.endswith(ext)


def test_upload_request_rejects_bad_extension(tmp_path: Path) -> None:
    bad = tmp_path / "clip.txt"
    bad.write_text("nope")
    with pytest.raises(ValidationError):
        VideoJobRequest(
            source_type=SourceType.UPLOAD,
            upload_path=str(bad),
        )


def test_script_request_requires_text() -> None:
    with pytest.raises(ValidationError):
        VideoJobRequest(source_type=SourceType.SCRIPT, script_text="   ")


def test_script_request_valid() -> None:
    req = VideoJobRequest(
        source_type=SourceType.SCRIPT,
        script_text="Hello world from a script.",
    )
    assert req.script_text.startswith("Hello")


def test_feature_flag_defaults() -> None:
    flags = FeatureFlags()
    assert flags.viral_moments is True
    assert flags.important_moments is True
    assert flags.platform_optimization is True
    assert flags.b_roll is False
    assert flags.cinematic_moments is False
    assert flags.expert_insights is False
    assert flags.best_quotes is False
    assert flags.podcast_clips is False
    assert flags.research is False
    assert flags.supervisor_crew is False
    assert flags.content_calendar is False
    assert flags.brand is False


def test_target_clip_duration_options() -> None:
    for d in (10, 15, 30, 40, 45, 60, 90):
        cfg = VideoJobConfig(target_clip_duration=d)
        assert cfg.target_clip_duration == d
    with pytest.raises(ValidationError):
        VideoJobConfig(target_clip_duration=20)  # type: ignore[arg-type]
    assert VideoJobConfig().short_durations == [30, 60, 90]
    assert FeatureFlags().multi_shorts_export is False
    assert FeatureFlags().scene_transform is False
