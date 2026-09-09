"""Best-effort YouTube media download via yt-dlp (authorized content only)."""

from __future__ import annotations

import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config.settings import get_settings
from core.logging import get_logger
from ingestion.errors import (
    YouTubeDownloadError,
    YouTubeDownloadStatus,
    classify_ytdlp_error,
)

logger = get_logger(__name__)

DEFAULT_FORMAT = "bv*+ba/b"
_MEDIA_SUFFIXES = {".mp4", ".mkv", ".webm", ".m4a", ".mp3", ".wav", ".mov"}


@dataclass(slots=True)
class YouTubeDownloadResult:
    status: YouTubeDownloadStatus
    local_path: str = ""
    video_id: str = ""
    title: str = ""
    error: YouTubeDownloadError | None = None

    @property
    def ok(self) -> bool:
        return self.status == YouTubeDownloadStatus.SUCCESS and bool(self.local_path)


def _cookies_allowed(settings: Any) -> str:
    """Return cookie file path only for non-cloud local use when explicitly set."""
    raw = str(getattr(settings, "youtube_cookies_file", "") or "").strip()
    if not raw:
        return ""
    # Never use personal browser cookies on Streamlit Cloud
    if getattr(settings, "is_streamlit_cloud", False):
        logger.warning(
            "YOUTUBE_COOKIES_FILE ignored on Streamlit Cloud "
            "(do not store personal browser cookies)."
        )
        return ""
    path = Path(raw)
    if not path.is_file():
        raise YouTubeDownloadError(
            YouTubeDownloadStatus.EXTRACTOR_ERROR.value,
            f"YOUTUBE_COOKIES_FILE not found: {path}",
            retryable=False,
            status=YouTubeDownloadStatus.EXTRACTOR_ERROR,
        )
    return str(path.resolve())


def _pick_downloaded_file(prepared: Path, source_dir: Path, video_id: str) -> Path:
    candidates = [
        prepared,
        prepared.with_suffix(".mp4"),
        prepared.with_suffix(".mkv"),
        prepared.with_suffix(".webm"),
        source_dir / f"{video_id}.mp4",
        source_dir / f"{video_id}.mkv",
        source_dir / f"{video_id}.webm",
    ]
    seen: set[Path] = set()
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if path.exists() and path.is_file() and path.stat().st_size > 0:
            return path.resolve()

    matches = sorted(
        p
        for p in source_dir.iterdir()
        if p.is_file()
        and p.stem.startswith(video_id)
        and p.suffix.lower() in _MEDIA_SUFFIXES
        and p.stat().st_size > 0
    )
    if matches:
        return matches[0].resolve()
    raise YouTubeDownloadError(
        YouTubeDownloadStatus.EXTRACTOR_ERROR.value,
        "Downloaded YouTube media could not be located under the download directory.",
        retryable=False,
        status=YouTubeDownloadStatus.EXTRACTOR_ERROR,
    )


def _run_ytdlp(
    url: str,
    source_dir: Path,
    *,
    video_id: str,
    format_value: str,
    cookies_file: str,
    ffmpeg_path: str,
) -> tuple[Path, dict[str, Any]]:
    try:
        import yt_dlp
        from yt_dlp.utils import DownloadError
    except ImportError as exc:  # pragma: no cover
        raise YouTubeDownloadError(
            YouTubeDownloadStatus.EXTRACTOR_ERROR.value,
            "yt-dlp is not installed. Run: pip install yt-dlp",
            retryable=False,
            status=YouTubeDownloadStatus.EXTRACTOR_ERROR,
        ) from exc

    outtmpl = str(source_dir / f"{video_id}.%(ext)s")
    ydl_opts: dict[str, Any] = {
        "outtmpl": outtmpl,
        "format": format_value or DEFAULT_FORMAT,
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "retries": 2,
        "fragment_retries": 2,
        "concurrent_fragment_downloads": 1,
    }
    if cookies_file:
        ydl_opts["cookiefile"] = cookies_file
    if ffmpeg_path:
        ydl_opts["ffmpeg_location"] = ffmpeg_path

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not isinstance(info, dict):
                raise YouTubeDownloadError(
                    YouTubeDownloadStatus.EXTRACTOR_ERROR.value,
                    "yt-dlp returned no media info.",
                    retryable=False,
                    status=YouTubeDownloadStatus.EXTRACTOR_ERROR,
                )
            prepared = Path(ydl.prepare_filename(info))
            media = _pick_downloaded_file(prepared, source_dir, video_id)
            return media, info
    except YouTubeDownloadError:
        raise
    except DownloadError as exc:
        raise classify_ytdlp_error(exc) from exc
    except Exception as exc:  # noqa: BLE001
        raise classify_ytdlp_error(exc) from exc


def download_youtube(
    url: str,
    *,
    dest_dir: Path | str | None = None,
    keep_temp: bool = False,
) -> YouTubeDownloadResult:
    """Download ``url`` with yt-dlp into dest_dir or a temp directory.

    On failure returns ``YouTubeDownloadResult`` with ``error`` set (does not
    crash the process). Callers that prefer exceptions can raise ``result.error``.
    """
    settings = get_settings()
    raw_url = (url or "").strip()
    logger.info("SOURCE_REQUESTED type=youtube")
    if not raw_url:
        err = YouTubeDownloadError(
            YouTubeDownloadStatus.EXTRACTOR_ERROR.value,
            "YouTube URL is empty.",
            retryable=False,
            status=YouTubeDownloadStatus.EXTRACTOR_ERROR,
        )
        return YouTubeDownloadResult(status=err.status, error=err)

    if not settings.youtube_download_enabled:
        err = YouTubeDownloadError(
            YouTubeDownloadStatus.EXTRACTOR_ERROR.value,
            "YouTube download is disabled (YOUTUBE_DOWNLOAD_ENABLED=false).",
            retryable=False,
            status=YouTubeDownloadStatus.EXTRACTOR_ERROR,
        )
        return YouTubeDownloadResult(status=err.status, error=err)

    from tools.ffmpeg.bin import resolve_ffmpeg_binary
    from tools.youtube.urls import extract_video_id, normalize_youtube_url

    try:
        normalized = normalize_youtube_url(raw_url)
        video_id = extract_video_id(normalized) or "youtube_video"
    except Exception as exc:  # noqa: BLE001
        err = YouTubeDownloadError(
            YouTubeDownloadStatus.EXTRACTOR_ERROR.value,
            f"Invalid YouTube URL: {exc}",
            retryable=False,
            status=YouTubeDownloadStatus.EXTRACTOR_ERROR,
        )
        return YouTubeDownloadResult(status=err.status, error=err)

    ffmpeg_path = (settings.ffmpeg_path or "").strip() or (resolve_ffmpeg_binary() or "")
    if not ffmpeg_path:
        err = YouTubeDownloadError(
            YouTubeDownloadStatus.EXTRACTOR_ERROR.value,
            "FFmpeg is required for YouTube media merge. Install FFmpeg or set FFMPEG_PATH.",
            retryable=False,
            status=YouTubeDownloadStatus.EXTRACTOR_ERROR,
        )
        return YouTubeDownloadResult(status=err.status, video_id=video_id, error=err)

    try:
        cookies = _cookies_allowed(settings)
    except YouTubeDownloadError as exc:
        return YouTubeDownloadResult(status=exc.status, video_id=video_id, error=exc)

    format_value = (settings.youtube_download_format or DEFAULT_FORMAT).strip() or DEFAULT_FORMAT
    formats = [format_value]
    if format_value != DEFAULT_FORMAT:
        formats.append(DEFAULT_FORMAT)

    owns_temp = dest_dir is None
    temp_root: tempfile.TemporaryDirectory[str] | None = None
    if dest_dir is None:
        temp_root = tempfile.TemporaryDirectory(prefix="yt_ingest_")
        source_dir = Path(temp_root.name)
    else:
        source_dir = Path(dest_dir)
        source_dir.mkdir(parents=True, exist_ok=True)

    logger.info("YOUTUBE_DOWNLOAD_STARTED video_id=%s", video_id)
    last_error: YouTubeDownloadError | None = None
    max_attempts = 3
    try:
        for format_index, fmt in enumerate(formats):
            for attempt in range(max_attempts):
                try:
                    media, info = _run_ytdlp(
                        normalized,
                        source_dir,
                        video_id=video_id,
                        format_value=fmt,
                        cookies_file=cookies,
                        ffmpeg_path=ffmpeg_path,
                    )
                    # Optionally copy out of temp into a stable caller path
                    final_path = media
                    if owns_temp and keep_temp:
                        # Caller asked to keep file: copy beside temp into media dir
                        from core.paths import ensure_media_dir

                        stable = ensure_media_dir() / media.name
                        shutil.copy2(media, stable)
                        final_path = stable.resolve()
                    elif not owns_temp:
                        final_path = media.resolve()
                    else:
                        # Persist into media dir so temp cleanup does not delete it
                        from core.paths import ensure_media_dir

                        stable = ensure_media_dir() / f"{video_id}{media.suffix.lower() or '.mp4'}"
                        shutil.copy2(media, stable)
                        final_path = stable.resolve()

                    title = str(info.get("title") or "")
                    logger.info(
                        "YOUTUBE_DOWNLOAD_SUCCEEDED video_id=%s path=%s",
                        video_id,
                        final_path,
                    )
                    return YouTubeDownloadResult(
                        status=YouTubeDownloadStatus.SUCCESS,
                        local_path=str(final_path),
                        video_id=video_id,
                        title=title,
                    )
                except YouTubeDownloadError as exc:
                    last_error = exc
                except Exception as exc:  # noqa: BLE001
                    last_error = classify_ytdlp_error(exc)

                if last_error is None:
                    continue
                if last_error.retryable and attempt + 1 < max_attempts:
                    delay = 2**attempt
                    logger.warning(
                        "YOUTUBE_DOWNLOAD_FAILED retryable code=%s attempt=%s",
                        last_error.code,
                        attempt + 1,
                    )
                    time.sleep(delay)
                    continue
                if format_index + 1 < len(formats):
                    break
                logger.warning(
                    "YOUTUBE_DOWNLOAD_FAILED code=%s status=%s",
                    last_error.code,
                    last_error.status.value,
                )
                return YouTubeDownloadResult(
                    status=last_error.status, video_id=video_id, error=last_error
                )
        assert last_error is not None
        logger.warning(
            "YOUTUBE_DOWNLOAD_FAILED code=%s status=%s",
            last_error.code,
            last_error.status.value,
        )
        return YouTubeDownloadResult(
            status=last_error.status, video_id=video_id, error=last_error
        )
    finally:
        if temp_root is not None:
            temp_root.cleanup()


def download_youtube_or_raise(url: str, *, dest_dir: Path | str | None = None) -> Path:
    """Download and return path, or raise ``YouTubeDownloadError``."""
    result = download_youtube(url, dest_dir=dest_dir)
    if result.ok:
        return Path(result.local_path)
    if result.error:
        raise result.error
    raise YouTubeDownloadError(
        YouTubeDownloadStatus.UNKNOWN.value,
        "YouTube download failed.",
        retryable=False,
    )
