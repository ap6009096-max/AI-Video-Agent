"""Central media path validation and source resolution."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from core.errors import InputValidationError, StorageError, YouTubeAgentError
from core.logging import get_logger
from core.paths import ensure_media_dir

logger = get_logger(__name__)


def validate_media_path(path: str | Path | None) -> str:
    """Return an absolute path to an existing non-empty media file."""
    if not path:
        raise ValueError("No media path was provided.")

    media_path = Path(path).expanduser().resolve()

    if not media_path.exists():
        raise FileNotFoundError(f"Media file does not exist: {media_path}")

    if not media_path.is_file():
        raise ValueError(f"Media path is not a file: {media_path}")

    if media_path.stat().st_size == 0:
        raise ValueError(f"Media file is empty: {media_path}")

    return str(media_path)


def save_uploaded_media(uploaded_file: Any, *, job_id: str | None = None) -> str:
    """Persist a Streamlit UploadedFile (or file-like) into OUTPUT_DIR/media."""
    media_dir = ensure_media_dir()
    raw_name = getattr(uploaded_file, "name", None) or "upload.bin"
    safe_name = Path(str(raw_name)).name
    prefix = (job_id or str(uuid4())).strip() or str(uuid4())
    dest = media_dir / f"{prefix}_{safe_name}"

    try:
        if hasattr(uploaded_file, "getbuffer"):
            dest.write_bytes(uploaded_file.getbuffer())
        elif hasattr(uploaded_file, "read"):
            data = uploaded_file.read()
            if isinstance(data, str):
                data = data.encode("utf-8")
            dest.write_bytes(data)
        else:
            raise InputValidationError("Uploaded file object is not readable.")
    except OSError as exc:
        raise StorageError(f"Failed to save upload: {dest}") from exc

    validated = validate_media_path(dest)
    size = Path(validated).stat().st_size
    logger.info("[MEDIA] Input type: upload")
    logger.info("[MEDIA] Local path: %s", validated)
    logger.info("[MEDIA] File exists: True")
    logger.info("[MEDIA] File size: %s", size)
    return validated


def download_youtube_media(url: str, *, dest_dir: Path | None = None) -> str:
    """Download YouTube media via yt-dlp into dest_dir (default OUTPUT_DIR/media)."""
    from tools.youtube.ytdlp_provider import download_youtube_media as _download

    target = dest_dir or ensure_media_dir()
    target.mkdir(parents=True, exist_ok=True)
    logger.info("[MEDIA] Input type: youtube")
    logger.info("[MEDIA] Downloading YouTube media")
    try:
        path = _download(url.strip(), target)
    except YouTubeAgentError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("YouTube media download failed")
        raise YouTubeAgentError(f"YouTube media download failed: {exc}") from exc

    validated = validate_media_path(path)
    size = Path(validated).stat().st_size
    logger.info("[MEDIA] Download complete")
    logger.info("[MEDIA] Local path: %s", validated)
    logger.info("[MEDIA] File exists: True")
    logger.info("[MEDIA] File size: %s", size)
    return validated


def resolve_media_source(
    *,
    uploaded_file: Any = None,
    youtube_url: str | None = None,
    existing_media_path: str | None = None,
    job_id: str | None = None,
) -> str:
    """Return exactly one validated local media path.

    Priority: uploaded_file → youtube_url → existing_media_path → error.
    """
    if uploaded_file is not None:
        return save_uploaded_media(uploaded_file, job_id=job_id)

    url = (youtube_url or "").strip()
    if url:
        return download_youtube_media(url)

    if existing_media_path:
        return validate_media_path(existing_media_path)

    raise ValueError("Please upload a video or provide a YouTube URL.")
