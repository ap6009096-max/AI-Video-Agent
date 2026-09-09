"""Workflow-oriented checks for YouTube soft-fail and storage handoff."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from ingestion.errors import USER_FACING_YOUTUBE_FAILURE, YouTubeDownloadStatus
from ingestion.youtube import YouTubeDownloadResult, download_youtube
from storage.local_storage import LocalObjectStorage
from storage.sync import persist_source_media


def test_youtube_failure_path_allows_upload_fallback(tmp_path: Path) -> None:
    """YouTube failure returns structured error; upload can still persist media."""
    with (
        patch("ingestion.youtube.get_settings") as gs,
        patch("tools.ffmpeg.bin.resolve_ffmpeg_binary", return_value="/bin/ffmpeg"),
        patch("tools.youtube.urls.normalize_youtube_url", return_value="https://youtu.be/z"),
        patch("tools.youtube.urls.extract_video_id", return_value="z"),
        patch(
            "ingestion.youtube._run_ytdlp",
            side_effect=Exception("ERROR: [youtube] z: Video unavailable."),
        ),
    ):
        settings = MagicMock()
        settings.youtube_download_enabled = True
        settings.youtube_download_format = "bv*+ba/b"
        settings.youtube_cookies_file = ""
        settings.ffmpeg_path = ""
        settings.is_streamlit_cloud = False
        gs.return_value = settings
        result = download_youtube("https://youtu.be/z", dest_dir=tmp_path)

    assert isinstance(result, YouTubeDownloadResult)
    assert result.ok is False
    assert result.error is not None
    assert result.error.status == YouTubeDownloadStatus.UNAVAILABLE
    assert "could not be downloaded" in USER_FACING_YOUTUBE_FAILURE.lower()

    # Fallback upload still works against local durable mirror
    storage = LocalObjectStorage(bucket="wf", root=tmp_path / "objects")
    media = tmp_path / "fallback.mp4"
    media.write_bytes(b"uploaded-instead")
    with patch("storage.sync.get_object_storage", return_value=storage):
        ref = persist_source_media(
            project_id="fallback1",
            local_path=media,
            source_type="upload",
        )
    assert storage.file_exists(ref.storage_path)
    assert ref.source_type == "upload"


def test_youtube_success_persists_to_storage(tmp_path: Path) -> None:
    media = tmp_path / "ok.mp4"
    media.write_bytes(b"yt-bytes")
    storage = LocalObjectStorage(bucket="wf", root=tmp_path / "objects")
    with patch("storage.sync.get_object_storage", return_value=storage):
        ref = persist_source_media(
            project_id="ytok",
            local_path=media,
            source_type="youtube",
            source_url="https://youtu.be/ok",
        )
    assert ref.storage_path.startswith("projects/ytok/source/")
    assert storage.file_exists(ref.storage_path)
