"""Tests for the Input Agent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.input_agent import InputAgent
from config.settings import get_settings
from core.errors import InputValidationError
from core.paths import get_project_dir
from schemas.job import SourceType, VideoJobRequest
from schemas.project import DownstreamRoute


def test_project_metadata_requires_source_type() -> None:
    from pydantic import ValidationError
    from schemas.project import ProjectMetadata

    with pytest.raises(ValidationError, match="source_type"):
        ProjectMetadata.model_validate({})


def test_missing_ui_source_raises_clear_error() -> None:
    from ui.job_runner import build_job_request

    with pytest.raises(ValueError, match="Unable to determine source type"):
        build_job_request({}, {}, {})


def test_youtube_happy_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()

    request = VideoJobRequest(
        job_id="proj-yt-1",
        source_type=SourceType.YOUTUBE,
        youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    )
    result = InputAgent().run(request)

    assert result.detected_source_type == SourceType.YOUTUBE
    assert result.next_agent == DownstreamRoute.YOUTUBE_INGEST
    assert result.project.project_id == "proj-yt-1"
    assert result.project.youtube_url.startswith("https://")
    assert result.project.source_path == ""
    assert result.project.raw_text == ""

    project_json = Path(result.project_dir) / "project.json"
    assert project_json.is_file()
    data = json.loads(project_json.read_text(encoding="utf-8"))
    assert data["project_id"] == "proj-yt-1"
    assert data["source_type"] == "youtube"
    assert "configuration" in data
    assert data["configuration"]["config"]["platform"]
    get_settings.cache_clear()


def test_upload_happy_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()

    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake-video-bytes")

    request = VideoJobRequest(
        job_id="proj-up-1",
        source_type=SourceType.UPLOAD,
        upload_path=str(video),
    )
    result = InputAgent().run(request)

    assert result.next_agent == DownstreamRoute.LOCAL_VIDEO_INGEST
    assert result.detected_source_type == SourceType.UPLOAD
    assert result.project.source_type == SourceType.UPLOAD
    assert result.project.source_path == str(video)
    assert (Path(result.project_dir) / "project.json").is_file()
    get_settings.cache_clear()


def test_audio_upload_uses_upload_source_type(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()

    audio = tmp_path / "podcast.mp3"
    audio.write_bytes(b"fake-audio-bytes")
    result = InputAgent().run(
        VideoJobRequest(
            job_id="proj-audio-1",
            source_type=SourceType.UPLOAD,
            upload_path=str(audio),
        )
    )

    assert result.detected_source_type == SourceType.UPLOAD
    assert result.project.source_type == SourceType.UPLOAD
    assert json.loads(
        (Path(result.project_dir) / "project.json").read_text(encoding="utf-8")
    )["source_type"] == SourceType.UPLOAD.value
    get_settings.cache_clear()


def test_upload_rejects_bad_extension(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()

    bad = tmp_path / "clip.txt"
    bad.write_text("nope")

    # Bypass VideoJobRequest extension check by constructing via model_construct
    request = VideoJobRequest.model_construct(
        job_id="bad-ext",
        source_type=SourceType.UPLOAD,
        upload_path=str(bad),
        youtube_url="",
        script_text="",
    )
    with pytest.raises(InputValidationError, match="Unsupported upload format"):
        InputAgent().run(request)
    get_settings.cache_clear()


def test_upload_rejects_oversized(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("MAX_UPLOAD_MB", "0")
    get_settings.cache_clear()

    video = tmp_path / "big.mp4"
    video.write_bytes(b"x" * 2048)

    request = VideoJobRequest(
        job_id="big-file",
        source_type=SourceType.UPLOAD,
        upload_path=str(video),
    )
    with pytest.raises(InputValidationError, match="maximum size"):
        InputAgent().run(request)
    get_settings.cache_clear()


def test_script_empty_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()

    request = VideoJobRequest.model_construct(
        job_id="empty-script",
        source_type=SourceType.SCRIPT,
        script_text="   ",
        youtube_url="",
        upload_path="",
    )
    with pytest.raises(InputValidationError, match="Script text"):
        InputAgent().run(request)
    get_settings.cache_clear()


def test_script_happy_path_creates_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()

    request = VideoJobRequest(
        job_id="script-1",
        source_type=SourceType.SCRIPT,
        script_text="Hello from the script.",
    )
    result = InputAgent().run(request)

    assert result.next_agent == DownstreamRoute.SCRIPT_INGEST
    assert result.project.raw_text == "Hello from the script."
    assert get_project_dir("script-1").is_dir()
    get_settings.cache_clear()


def test_youtube_rejects_non_youtube(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()

    request = VideoJobRequest.model_construct(
        job_id="bad-yt",
        source_type=SourceType.YOUTUBE,
        youtube_url="https://example.com/watch?v=1",
        upload_path="",
        script_text="",
    )
    with pytest.raises(InputValidationError, match="YouTube"):
        InputAgent().run(request)
    get_settings.cache_clear()
