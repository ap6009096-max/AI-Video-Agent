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

# Progressive first (no FFmpeg merge); merge formats last.
PROGRESSIVE_FORMAT = "best[height<=720][ext=mp4]/best[height<=720]/best"
# Prefer HTTPS progressive streams over HLS (m3u8) — much faster / more reliable in UI.
HTTPS_MERGE_FORMAT = (
    "bv*[height<=720][ext=mp4]+ba[ext=m4a]/"
    "bestvideo[height<=720][protocol^=http]+bestaudio[protocol^=http]/"
    "bv*+ba/b"
)
MERGE_FORMAT = "bv*+ba/b"
DEFAULT_FORMAT = HTTPS_MERGE_FORMAT
SOCKET_TIMEOUT_SEC = 30
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


def _format_needs_ffmpeg(format_value: str) -> bool:
    """Split-stream formats (contain '+') need FFmpeg to merge."""
    return "+" in (format_value or "")


def _build_format_chain(
    settings_format: str, *, ffmpeg_available: bool = True
) -> list[str]:
    """Ordered formats for yt-dlp.

    Modern YouTube often exposes only separate video/audio streams (no progressive
    A+V). Prefer merge when FFmpeg is available; keep progressive as fallback.
    """
    configured = (settings_format or "").strip()
    chain: list[str] = []
    if ffmpeg_available:
        candidates = (
            HTTPS_MERGE_FORMAT,
            MERGE_FORMAT,
            "bestvideo[height<=720]+bestaudio/best",
            configured,
            PROGRESSIVE_FORMAT,
            "best",
        )
    else:
        candidates = (configured, PROGRESSIVE_FORMAT, "best")
    for fmt in candidates:
        if not fmt or fmt in chain:
            continue
        if not ffmpeg_available and _format_needs_ffmpeg(fmt):
            continue
        chain.append(fmt)
    return chain or [PROGRESSIVE_FORMAT]


def _resolve_js_runtimes() -> dict[str, dict[str, str]]:
    """Enable Node/Deno for yt-dlp YouTube EJS when available on PATH."""
    import shutil

    runtimes: dict[str, dict[str, str]] = {}
    node = shutil.which("node")
    if node:
        runtimes["node"] = {"path": node}
    deno = shutil.which("deno")
    if deno:
        runtimes["deno"] = {"path": deno}
    return runtimes


def _cookies_allowed(settings: Any) -> str:
    """Return cookie file path only for non-cloud local use when explicitly set."""
    raw = str(getattr(settings, "youtube_cookies_file", "") or "").strip()
    if not raw:
        return ""
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


def _cleanup_partials(source_dir: Path, video_id: str) -> None:
    """Remove incomplete yt-dlp artifacts for this video_id."""
    if not source_dir.is_dir():
        return
    for path in source_dir.glob(f"{video_id}*"):
        try:
            if path.is_file():
                path.unlink()
                logger.debug("Cleaned partial download: %s", path.name)
        except OSError as exc:
            logger.warning("Could not remove partial %s: %s", path, exc)


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


def _yt_dlp_version() -> str:
    try:
        import yt_dlp.version

        return str(getattr(yt_dlp.version, "__version__", "unknown"))
    except Exception:  # noqa: BLE001
        return "unknown"


def _run_ytdlp(
    url: str,
    source_dir: Path,
    *,
    video_id: str,
    format_value: str,
    cookies_file: str,
    ffmpeg_path: str,
    debug: bool = False,
) -> tuple[Path, dict[str, Any]]:
    try:
        import yt_dlp
        from yt_dlp.utils import DownloadError
    except ImportError as exc:  # pragma: no cover
        raise YouTubeDownloadError(
            YouTubeDownloadStatus.EXTRACTOR_ERROR.value,
            "yt-dlp is not installed. Run: pip install -U yt-dlp",
            retryable=False,
            status=YouTubeDownloadStatus.EXTRACTOR_ERROR,
        ) from exc

    outtmpl = str(source_dir / f"{video_id}.%(ext)s")
    ydl_opts: dict[str, Any] = {
        "outtmpl": outtmpl,
        "format": format_value or (
            MERGE_FORMAT if ffmpeg_path else PROGRESSIVE_FORMAT
        ),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": not debug,
        "no_warnings": not debug,
        "noprogress": True,
        "retries": 2,
        "fragment_retries": 2,
        "concurrent_fragment_downloads": 1,
        "socket_timeout": SOCKET_TIMEOUT_SEC,
    }
    js_runtimes = _resolve_js_runtimes()
    if js_runtimes:
        ydl_opts["js_runtimes"] = js_runtimes
        # Needed so Node can solve YouTube n/sig challenges and unlock HTTPS formats.
        ydl_opts["remote_components"] = {"ejs:github"}
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


def _resolve_ffmpeg() -> str:
    """Resolve FFmpeg binary path; empty string if unavailable."""
    try:
        from tools.ffmpeg.bin import resolve_ffmpeg_binary

        return (resolve_ffmpeg_binary() or "").strip()
    except Exception:  # noqa: BLE001
        logger.warning("FFmpeg resolution failed; continuing without merge support")
        return ""


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

    ffmpeg_path = (settings.ffmpeg_path or "").strip() or _resolve_ffmpeg()
    debug = (
        str(getattr(settings, "app_env", "") or "").lower() == "development"
        or str(getattr(settings, "log_level", "") or "").upper() == "DEBUG"
    )

    try:
        cookies = _cookies_allowed(settings)
    except YouTubeDownloadError as exc:
        return YouTubeDownloadResult(status=exc.status, video_id=video_id, error=exc)

    formats = _build_format_chain(
        str(getattr(settings, "youtube_download_format", "") or ""),
        ffmpeg_available=bool(ffmpeg_path),
    )
    # Drop merge formats when FFmpeg is unavailable; keep progressive attempts.
    runnable_formats: list[str] = []
    skipped_merge = False
    for fmt in formats:
        if _format_needs_ffmpeg(fmt) and not ffmpeg_path:
            skipped_merge = True
            logger.info(
                "YOUTUBE_FORMAT_SKIPPED reason=no_ffmpeg format=%s",
                fmt,
            )
            continue
        runnable_formats.append(fmt)


    if not runnable_formats:
        err = YouTubeDownloadError(
            YouTubeDownloadStatus.EXTRACTOR_ERROR.value,
            "FFmpeg is required for YouTube media merge. "
            "Install FFmpeg, set FFMPEG_PATH, or install imageio-ffmpeg. "
            "Alternatively upload the video file directly.",
            retryable=False,
            status=YouTubeDownloadStatus.EXTRACTOR_ERROR,
        )
        return YouTubeDownloadResult(status=err.status, video_id=video_id, error=err)

    owns_temp = dest_dir is None
    temp_root: tempfile.TemporaryDirectory[str] | None = None
    if dest_dir is None:
        temp_root = tempfile.TemporaryDirectory(prefix="yt_ingest_")
        source_dir = Path(temp_root.name)
    else:
        source_dir = Path(dest_dir)
        source_dir.mkdir(parents=True, exist_ok=True)

    logger.info(
        "YOUTUBE_DOWNLOAD_STARTED video_id=%s yt_dlp=%s formats=%s ffmpeg=%s",
        video_id,
        _yt_dlp_version(),
        runnable_formats,
        bool(ffmpeg_path),
    )
    last_error: YouTubeDownloadError | None = None
    max_attempts = 3
    try:
        for format_index, fmt in enumerate(runnable_formats):
            for attempt in range(max_attempts):
                _cleanup_partials(source_dir, video_id)
                logger.info(
                    "YOUTUBE_DOWNLOAD_ATTEMPT video_id=%s format=%s attempt=%s",
                    video_id,
                    fmt,
                    attempt + 1,
                )
                try:
                    media, info = _run_ytdlp(
                        normalized,
                        source_dir,
                        video_id=video_id,
                        format_value=fmt,
                        cookies_file=cookies,
                        ffmpeg_path=ffmpeg_path,
                        debug=debug,
                    )
                    final_path = media
                    if owns_temp and keep_temp:
                        from core.paths import ensure_media_dir

                        stable = ensure_media_dir() / media.name
                        shutil.copy2(media, stable)
                        final_path = stable.resolve()
                    elif not owns_temp:
                        final_path = media.resolve()
                    else:
                        from core.paths import ensure_media_dir

                        stable = (
                            ensure_media_dir()
                            / f"{video_id}{media.suffix.lower() or '.mp4'}"
                        )
                        shutil.copy2(media, stable)
                        final_path = stable.resolve()

                    size = final_path.stat().st_size if final_path.is_file() else 0
                    title = str(info.get("title") or "")
                    logger.info(
                        "YOUTUBE_DOWNLOAD_SUCCEEDED video_id=%s path=%s size=%s format=%s",
                        video_id,
                        final_path,
                        size,
                        fmt,
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

                _cleanup_partials(source_dir, video_id)
                if last_error is None:
                    continue
                logger.warning(
                    "YOUTUBE_DOWNLOAD_FAILED code=%s status=%s format=%s attempt=%s detail=%s",
                    last_error.code,
                    last_error.status.value,
                    fmt,
                    attempt + 1,
                    last_error.message[:200],
                )
                if last_error.retryable and attempt + 1 < max_attempts:
                    delay = 2**attempt
                    time.sleep(delay)
                    continue
                if format_index + 1 < len(runnable_formats):
                    break
                return YouTubeDownloadResult(
                    status=last_error.status, video_id=video_id, error=last_error
                )

        assert last_error is not None
        if skipped_merge and last_error.status != YouTubeDownloadStatus.EXTRACTOR_ERROR:
            # Progressive failed; note that merge was unavailable
            logger.info(
                "YOUTUBE_DOWNLOAD_NOTE progressive_failed_merge_skipped_no_ffmpeg"
            )
        return YouTubeDownloadResult(
            status=last_error.status, video_id=video_id, error=last_error
        )
    finally:
        if temp_root is not None:
            try:
                temp_root.cleanup()
            except Exception:  # noqa: BLE001
                logger.warning("Temp download directory cleanup failed")


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
