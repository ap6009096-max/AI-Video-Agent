"""Tests for YouTube ingestion error classification and download wrapper."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ingestion.errors import (
    YouTubeDownloadError,
    YouTubeDownloadStatus,
    classify_ytdlp_error,
)
from ingestion.youtube import download_youtube


def test_classify_403() -> None:
    err = classify_ytdlp_error(Exception("HTTP Error 403: Forbidden"))
    assert err.status == YouTubeDownloadStatus.FORBIDDEN
    assert err.code == "forbidden"
    assert err.retryable is False


def test_classify_unavailable() -> None:
    err = classify_ytdlp_error(Exception("ERROR: [youtube] abc: Video unavailable"))
    assert err.status == YouTubeDownloadStatus.UNAVAILABLE


def test_classify_private() -> None:
    err = classify_ytdlp_error(Exception("Private video. Sign in if you've been granted access"))
    assert err.status in {
        YouTubeDownloadStatus.RESTRICTED,
        YouTubeDownloadStatus.AUTHENTICATION_REQUIRED,
    }


def test_classify_network_retryable() -> None:
    err = classify_ytdlp_error(Exception("URLError: timed out"))
    assert err.status == YouTubeDownloadStatus.NETWORK_ERROR
    assert err.retryable is True


def test_invalid_url() -> None:
    result = download_youtube("not-a-url")
    assert result.ok is False
    assert result.error is not None
    assert result.error.status == YouTubeDownloadStatus.EXTRACTOR_ERROR


def test_empty_url() -> None:
    result = download_youtube("")
    assert result.ok is False
    assert result.error is not None


def test_download_success_mocked(tmp_path: Path) -> None:
    media = tmp_path / "vid123.mp4"
    media.write_bytes(b"fake-mp4-bytes-not-empty")

    fake_info = {"title": "Demo", "id": "vid123"}

    class FakeYDL:
        def __init__(self, opts):  # noqa: ANN001
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, *args):  # noqa: ANN002
            return False

        def extract_info(self, url, download=True):  # noqa: ANN001
            assert download is True
            return fake_info

        def prepare_filename(self, info):  # noqa: ANN001
            return str(media)

    with (
        patch("ingestion.youtube.get_settings") as gs,
        patch("tools.ffmpeg.bin.resolve_ffmpeg_binary", return_value="/usr/bin/ffmpeg"),
        patch("tools.youtube.urls.normalize_youtube_url", return_value="https://youtu.be/vid123"),
        patch("tools.youtube.urls.extract_video_id", return_value="vid123"),
        patch.dict("sys.modules", {"yt_dlp": MagicMock(YoutubeDL=FakeYDL)}),
    ):
        settings = MagicMock()
        settings.youtube_download_enabled = True
        settings.youtube_download_format = "bv*+ba/b"
        settings.youtube_cookies_file = ""
        settings.ffmpeg_path = ""
        settings.is_streamlit_cloud = False
        gs.return_value = settings

        # Re-import path uses yt_dlp inside _run_ytdlp — patch there
        with patch("ingestion.youtube._run_ytdlp", return_value=(media, fake_info)):
            result = download_youtube(
                "https://www.youtube.com/watch?v=vid123",
                dest_dir=tmp_path,
            )
    assert result.ok is True
    assert Path(result.local_path).is_file()


def test_download_403_does_not_raise(tmp_path: Path) -> None:
    with (
        patch("ingestion.youtube.get_settings") as gs,
        patch("tools.ffmpeg.bin.resolve_ffmpeg_binary", return_value="/usr/bin/ffmpeg"),
        patch("tools.youtube.urls.normalize_youtube_url", return_value="https://youtu.be/x"),
        patch("tools.youtube.urls.extract_video_id", return_value="x"),
        patch(
            "ingestion.youtube._run_ytdlp",
            side_effect=YouTubeDownloadError(
                "forbidden",
                "YouTube rejected the media request with HTTP 403.",
                retryable=False,
                status=YouTubeDownloadStatus.FORBIDDEN,
            ),
        ),
    ):
        settings = MagicMock()
        settings.youtube_download_enabled = True
        settings.youtube_download_format = "bv*+ba/b"
        settings.youtube_cookies_file = ""
        settings.ffmpeg_path = ""
        settings.is_streamlit_cloud = False
        gs.return_value = settings
        result = download_youtube("https://youtu.be/x", dest_dir=tmp_path)
    assert result.ok is False
    assert result.error is not None
    assert result.error.status == YouTubeDownloadStatus.FORBIDDEN
