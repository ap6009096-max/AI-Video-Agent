"""Tests for central media resolve / validate (upload + YouTube + errors)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from config.settings import get_settings
from core.errors import YouTubeAgentError
from tools.media.resolve import (
    resolve_media_source,
    save_uploaded_media,
    validate_media_path,
)


def test_validate_media_path_ok(tmp_path: Path) -> None:
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"not-empty")
    assert validate_media_path(media) == str(media.resolve())


def test_validate_media_path_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="does not exist"):
        validate_media_path(tmp_path / "missing.mp4")


def test_validate_media_path_empty(tmp_path: Path) -> None:
    empty = tmp_path / "empty.mp4"
    empty.write_bytes(b"")
    with pytest.raises(ValueError, match="empty"):
        validate_media_path(empty)


def test_validate_media_path_none() -> None:
    with pytest.raises(ValueError, match="No media path"):
        validate_media_path(None)


def test_resolve_no_input() -> None:
    with pytest.raises(ValueError, match="upload a video or provide a YouTube URL"):
        resolve_media_source()


def test_resolve_upload_saves_to_media_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    uploaded = SimpleNamespace(name="demo.mp4", getbuffer=lambda: b"video-bytes")
    path = resolve_media_source(uploaded_file=uploaded, job_id="job1")
    assert Path(path).is_file()
    assert Path(path).stat().st_size > 0
    assert "media" in path.replace("\\", "/")
    assert Path(path).name.startswith("job1_")
    get_settings.cache_clear()


def test_resolve_youtube_uses_download(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()

    def _fake_download(url: str, dest_dir: Path) -> Path:
        out = Path(dest_dir) / "yt.mp4"
        out.write_bytes(b"downloaded")
        return out

    with patch("tools.youtube.ytdlp_provider.download_youtube_media", _fake_download):
        path = resolve_media_source(youtube_url="https://www.youtube.com/watch?v=abcdefghijk")
    assert Path(path).is_file()
    assert Path(path).read_bytes() == b"downloaded"
    get_settings.cache_clear()


def test_resolve_youtube_download_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()

    def _boom(url: str, dest_dir: Path) -> Path:
        raise YouTubeAgentError("YouTube media download failed: simulated")

    with patch("tools.youtube.ytdlp_provider.download_youtube_media", _boom):
        with pytest.raises(YouTubeAgentError, match="download failed"):
            resolve_media_source(youtube_url="https://www.youtube.com/watch?v=abcdefghijk")
    get_settings.cache_clear()


def test_resolve_existing_path(tmp_path: Path) -> None:
    media = tmp_path / "existing.mp4"
    media.write_bytes(b"x")
    assert resolve_media_source(existing_media_path=str(media)) == str(media.resolve())


def test_save_uploaded_media_rejects_empty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    uploaded = SimpleNamespace(name="empty.mp4", getbuffer=lambda: b"")
    with pytest.raises(ValueError, match="empty"):
        save_uploaded_media(uploaded, job_id="e1")
    get_settings.cache_clear()
