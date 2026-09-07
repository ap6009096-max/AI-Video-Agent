"""YouTube provider that downloads authorized media via yt-dlp."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from config.settings import get_settings
from core.errors import StorageError, YouTubeAgentError
from core.logging import get_logger
from schemas.youtube import (
    PreparedYouTubeSource,
    YouTubeSourceMetadata,
    YouTubeSourceStatus,
)
from tools.media.resolve import validate_media_path
from tools.youtube.oembed_provider import OEmbedYouTubeProvider

logger = get_logger(__name__)

DEFAULT_YTDLP_FORMAT = "best[height<=720]/best"

_SOURCE_README = """# YouTube source package

This directory stores YouTube source metadata and a local media copy downloaded
via yt-dlp for pipeline processing.

Only process content you are authorized to use, and comply with YouTube
platform terms and copyright requirements. FFmpeg must be on PATH when
yt-dlp needs to merge/remux streams.
"""

DownloadFn = Callable[[str, Path, dict[str, Any]], Path]


def _require_ffmpeg_hint() -> None:
    from tools.ffmpeg.bin import resolve_ffmpeg_binary

    if resolve_ffmpeg_binary() is None:
        raise YouTubeAgentError(
            "FFmpeg is required for video/audio processing. "
            "Please install FFmpeg and make sure it is available in PATH "
            "(or set FFMPEG_PATH)."
        )


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
        and p.suffix.lower() in {".mp4", ".mkv", ".webm", ".m4a", ".mp3", ".wav"}
        and p.stat().st_size > 0
    )
    if matches:
        return matches[0].resolve()
    raise YouTubeAgentError(
        "Downloaded YouTube media could not be located under the media directory."
    )


def _default_ytdlp_download(
    url: str,
    source_dir: Path,
    options: dict[str, Any],
) -> Path:
    """Download media with yt-dlp into ``source_dir``; return the media file path."""
    try:
        import yt_dlp
    except ImportError as exc:  # pragma: no cover
        raise YouTubeAgentError(
            "yt-dlp is not installed. Run: pip install yt-dlp"
        ) from exc

    _require_ffmpeg_hint()

    video_id = str(options.get("video_id") or "youtube_video")
    outtmpl = str(source_dir / f"{video_id}.%(ext)s")
    requested_format = str(options.get("format") or DEFAULT_YTDLP_FORMAT).strip()
    formats = [requested_format]
    if requested_format != DEFAULT_YTDLP_FORMAT:
        formats.append(DEFAULT_YTDLP_FORMAT)
    cookies = (options.get("cookies_file") or "").strip()
    if cookies:
        cookie_path = Path(cookies)
        if not cookie_path.is_file():
            raise YouTubeAgentError(
                f"YOUTUBE_COOKIES_FILE not found: {cookie_path}"
            )

    ffmpeg_path = (options.get("ffmpeg_path") or "").strip()

    last_error: Exception | None = None
    for index, format_value in enumerate(formats):
        ydl_opts: dict[str, Any] = {
            "outtmpl": outtmpl,
            "format": format_value,
            "merge_output_format": "mp4",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
        }
        if cookies:
            ydl_opts["cookiefile"] = str(cookie_path.resolve())
        if ffmpeg_path:
            ydl_opts["ffmpeg_location"] = ffmpeg_path

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if not isinstance(info, dict):
                    raise YouTubeAgentError("yt-dlp returned no media info.")
                prepared = Path(ydl.prepare_filename(info))
                media = _pick_downloaded_file(prepared, source_dir, video_id)
                return Path(validate_media_path(media))
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if index + 1 < len(formats):
                logger.warning(
                    "yt-dlp format failed; retrying with a compatible single-stream format"
                )
                continue

    assert last_error is not None
    if isinstance(last_error, YouTubeAgentError):
        raise last_error
    raise YouTubeAgentError(
        f"YouTube media download failed: {last_error}. "
        "Ensure FFmpeg is on PATH (or set FFMPEG_PATH), the video is "
        "publicly accessible, and you are authorized to process it."
    ) from last_error


def download_youtube_media(url: str, dest_dir: Path | str) -> Path:
    """Public helper: download ``url`` into ``dest_dir`` and return the file path."""
    settings = get_settings()
    target = Path(dest_dir)
    target.mkdir(parents=True, exist_ok=True)
    from tools.youtube.urls import extract_video_id

    try:
        video_id = extract_video_id(url)
    except Exception:  # noqa: BLE001
        video_id = "youtube_video"
    return _default_ytdlp_download(
        url,
        target,
        {
            "video_id": video_id or "youtube_video",
            "format": settings.youtube_download_format or DEFAULT_YTDLP_FORMAT,
            "cookies_file": settings.youtube_cookies_file,
            "ffmpeg_path": settings.ffmpeg_path,
        },
    )


class YtdlpYouTubeProvider:
    """oEmbed metadata + yt-dlp media download into project source/."""

    name = "ytdlp"

    def __init__(
        self,
        *,
        metadata_provider: OEmbedYouTubeProvider | None = None,
        download_fn: DownloadFn | None = None,
    ) -> None:
        self._meta = metadata_provider or OEmbedYouTubeProvider()
        self._download_fn = download_fn or _default_ytdlp_download

    def normalize_url(self, url: str) -> str:
        return self._meta.normalize_url(url)

    def fetch_metadata(self, url: str) -> YouTubeSourceMetadata:
        return self._meta.fetch_metadata(url)

    def prepare_source(
        self,
        project_dir: str | Path,
        metadata: YouTubeSourceMetadata,
    ) -> PreparedYouTubeSource:
        root = Path(project_dir)
        source_dir = root / "source"
        try:
            source_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise StorageError(f"Failed to create source directory: {source_dir}") from exc

        settings = get_settings()
        canonical = metadata.canonical_url or metadata.url
        video_id = metadata.video_id or "youtube_video"

        logger.info("[MEDIA] Input type: youtube")
        logger.info("[MEDIA] Downloading YouTube media")
        try:
            media_path = self._download_fn(
                canonical,
                source_dir,
                {
                    "video_id": video_id,
                    "format": settings.youtube_download_format or DEFAULT_YTDLP_FORMAT,
                    "cookies_file": settings.youtube_cookies_file,
                    "ffmpeg_path": settings.ffmpeg_path,
                },
            )
        except YouTubeAgentError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("YouTube media download failed")
            raise YouTubeAgentError(f"YouTube media download failed: {exc}") from exc

        media_path = Path(validate_media_path(media_path))

        # Prefer a stable filename for downstream tools.
        stable = source_dir / "youtube_video.mp4"
        if media_path.resolve() != stable.resolve():
            try:
                if media_path.suffix.lower() != ".mp4":
                    stable = source_dir / f"youtube_video{media_path.suffix.lower()}"
                if stable.exists() and stable.resolve() != media_path.resolve():
                    stable.unlink()
                media_path.replace(stable)
                media_path = stable
            except OSError:
                pass

        media_path = Path(validate_media_path(media_path))
        logger.info("[MEDIA] Download complete")
        logger.info("[MEDIA] Local path: %s", media_path)
        logger.info("[MEDIA] File exists: True")
        logger.info("[MEDIA] File size: %s", media_path.stat().st_size)

        prepared_meta = metadata.model_copy(
            update={
                "source_status": YouTubeSourceStatus.READY_FOR_PIPELINE,
                "provider": self.name,
                "notes": (
                    f"{metadata.notes} "
                    f"Downloaded local media via yt-dlp → {media_path.name}. "
                    "Only process content you are authorized to use."
                ).strip(),
            }
        )
        meta_path = source_dir / "source_metadata.json"
        try:
            payload = prepared_meta.model_dump(mode="json")
            payload["local_media_path"] = str(media_path.resolve())
            meta_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            (source_dir / "README.md").write_text(_SOURCE_README, encoding="utf-8")
        except OSError as exc:
            raise StorageError(f"Failed to write source metadata: {meta_path}") from exc

        return PreparedYouTubeSource(
            source_dir=str(source_dir.resolve()),
            metadata_path=str(meta_path.resolve()),
            local_media_path=str(media_path.resolve()),
            metadata=prepared_meta,
        )
