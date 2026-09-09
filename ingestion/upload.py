"""Direct media upload validation and durable storage staging."""

from __future__ import annotations

import mimetypes
import tempfile
from pathlib import Path
from typing import Any
from uuid import uuid4

from config.settings import get_settings
from core.logging import get_logger
from ingestion.errors import UploadValidationError
from storage import get_object_storage, upload_project_file
from storage.refs import MediaRef, path_safe_name

logger = get_logger(__name__)

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".mp3", ".wav", ".m4a"}
ALLOWED_MIME_PREFIXES = ("video/", "audio/")
ALLOWED_MIME_EXACT = {
    "video/mp4",
    "video/quicktime",
    "video/x-matroska",
    "video/webm",
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
    "audio/mp4",
    "audio/x-m4a",
    "application/octet-stream",
}


def validate_upload_bytes(
    *,
    filename: str,
    data: bytes,
    mime_type: str | None = None,
    max_upload_mb: int | None = None,
) -> tuple[str, str, int]:
    """Validate upload payload; return (safe_name, mime, size)."""
    settings = get_settings()
    limit_mb = int(max_upload_mb if max_upload_mb is not None else settings.max_upload_mb)
    safe = path_safe_name(filename)
    suffix = Path(safe).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise UploadValidationError(
            f"Unsupported file extension `{suffix or '(none)'}`. "
            f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    if not data or len(data) == 0:
        raise UploadValidationError("Uploaded file is empty.")
    size = len(data)
    max_bytes = max(1, limit_mb) * 1024 * 1024
    if size > max_bytes:
        raise UploadValidationError(
            f"File is too large ({size} bytes). Maximum allowed is {limit_mb} MB."
        )
    guessed = (mime_type or "").strip() or (mimetypes.guess_type(safe)[0] or "")
    if guessed and guessed not in ALLOWED_MIME_EXACT:
        if not any(guessed.startswith(p) for p in ALLOWED_MIME_PREFIXES):
            raise UploadValidationError(f"Unsupported MIME type: {guessed}")
    return safe, guessed or "application/octet-stream", size


def stage_upload_to_storage(
    uploaded_file: Any,
    *,
    project_id: str,
    max_upload_mb: int | None = None,
) -> MediaRef:
    """Validate Streamlit upload, write temp file, upload to object storage, cleanup temp."""
    logger.info("SOURCE_REQUESTED type=upload project_id=%s", project_id)
    logger.info("UPLOAD_STARTED project_id=%s", project_id)
    raw_name = getattr(uploaded_file, "name", None) or "upload.bin"
    mime_hint = getattr(uploaded_file, "type", None)

    if hasattr(uploaded_file, "getbuffer"):
        data = bytes(uploaded_file.getbuffer())
    elif hasattr(uploaded_file, "read"):
        raw = uploaded_file.read()
        data = raw.encode("utf-8") if isinstance(raw, str) else bytes(raw or b"")
    else:
        raise UploadValidationError("Uploaded file object is not readable.")

    safe_name, mime, size = validate_upload_bytes(
        filename=str(raw_name),
        data=data,
        mime_type=str(mime_hint or "") or None,
        max_upload_mb=max_upload_mb,
    )

    pid = (project_id or "").strip() or str(uuid4())
    storage = get_object_storage()

    with tempfile.TemporaryDirectory(prefix="upload_ingest_") as tmp:
        local = Path(tmp) / safe_name
        local.write_bytes(data)
        # Also keep a working copy under outputs/media for the pipeline
        from core.paths import ensure_media_dir

        working = ensure_media_dir() / f"{pid}_{safe_name}"
        working.write_bytes(data)
        try:
            ref = upload_project_file(
                storage,
                project_id=pid,
                category="source",
                local_path=working,
                filename=safe_name,
                content_type=mime,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("UPLOAD_FAILED project_id=%s err=%s", pid, type(exc).__name__)
            raise
        ref.local_path = str(working.resolve())
        ref.mime_type = mime
        ref.file_size = size
        ref.original_filename = safe_name
        ref.source_type = "upload"
        ref.status = "ready"
        logger.info(
            "UPLOAD_SUCCEEDED project_id=%s storage_path=%s size=%s",
            pid,
            ref.storage_path,
            size,
        )
        logger.info("STORAGE_UPLOAD_SUCCEEDED path=%s", ref.storage_path)
        return ref
