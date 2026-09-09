"""Media ingestion: YouTube (best-effort) and direct upload."""

from __future__ import annotations

from ingestion.errors import (
    USER_FACING_YOUTUBE_FAILURE,
    UploadValidationError,
    YouTubeDownloadError,
    YouTubeDownloadStatus,
    classify_ytdlp_error,
)
from ingestion.upload import stage_upload_to_storage, validate_upload_bytes
from ingestion.youtube import (
    YouTubeDownloadResult,
    download_youtube,
    download_youtube_or_raise,
)

__all__ = [
    "USER_FACING_YOUTUBE_FAILURE",
    "UploadValidationError",
    "YouTubeDownloadError",
    "YouTubeDownloadStatus",
    "YouTubeDownloadResult",
    "classify_ytdlp_error",
    "download_youtube",
    "download_youtube_or_raise",
    "stage_upload_to_storage",
    "validate_upload_bytes",
]
