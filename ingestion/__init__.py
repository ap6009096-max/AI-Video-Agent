"""Media ingestion: YouTube (best-effort) and direct upload.

Package init is intentionally empty of submodule imports so Streamlit Cloud
boot cannot fail on eager youtube/upload/storage loads. Access symbols via
``ingestion.errors`` / ``ingestion.youtube`` / ``ingestion.upload``, or via
lazy attribute access on this package.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "USER_FACING_YOUTUBE_FAILURE",
    "UploadValidationError",
    "YouTubeDownloadError",
    "YouTubeDownloadStatus",
    "YouTubeDownloadResult",
    "classify_ytdlp_error",
    "user_message_for_status",
    "user_message_for_youtube_error",
    "download_youtube",
    "download_youtube_or_raise",
    "stage_upload_to_storage",
    "validate_upload_bytes",
]

_LAZY_ATTRS: dict[str, tuple[str, str]] = {
    "USER_FACING_YOUTUBE_FAILURE": ("ingestion.errors", "USER_FACING_YOUTUBE_FAILURE"),
    "UploadValidationError": ("ingestion.errors", "UploadValidationError"),
    "YouTubeDownloadError": ("ingestion.errors", "YouTubeDownloadError"),
    "YouTubeDownloadStatus": ("ingestion.errors", "YouTubeDownloadStatus"),
    "classify_ytdlp_error": ("ingestion.errors", "classify_ytdlp_error"),
    "user_message_for_status": ("ingestion.errors", "user_message_for_status"),
    "user_message_for_youtube_error": (
        "ingestion.errors",
        "user_message_for_youtube_error",
    ),
    "YouTubeDownloadResult": ("ingestion.youtube", "YouTubeDownloadResult"),
    "download_youtube": ("ingestion.youtube", "download_youtube"),
    "download_youtube_or_raise": ("ingestion.youtube", "download_youtube_or_raise"),
    "stage_upload_to_storage": ("ingestion.upload", "stage_upload_to_storage"),
    "validate_upload_bytes": ("ingestion.upload", "validate_upload_bytes"),
}


def __getattr__(name: str) -> Any:
    target = _LAZY_ATTRS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr = target
    from importlib import import_module

    value = getattr(import_module(module_name), attr)
    globals()[name] = value
    return value
