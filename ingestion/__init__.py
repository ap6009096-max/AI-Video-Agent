"""Media ingestion: YouTube (best-effort) and direct upload.

Heavy submodules (youtube / upload → storage) load lazily so
``from ingestion.errors import ...`` does not pull the full stack at
Streamlit Cloud boot.
"""

from __future__ import annotations

from typing import Any

from ingestion.errors import (
    USER_FACING_YOUTUBE_FAILURE,
    UploadValidationError,
    YouTubeDownloadError,
    YouTubeDownloadStatus,
    classify_ytdlp_error,
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

_LAZY_ATTRS: dict[str, tuple[str, str]] = {
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
