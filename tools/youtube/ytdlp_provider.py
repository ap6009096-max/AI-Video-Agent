"""YouTube provider that downloads authorized media via yt-dlp."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from config.settings import get_settings
from core.errors import StorageError, YouTubeAgentError
from core.logging import get_logger
from ingestion.errors import YouTubeDownloadError
from ingestion.youtube import DEFAULT_FORMAT, download_youtube
from schemas.youtube import (
    PreparedYouTubeSource,
    YouTubeSourceMetadata,
    YouTubeSourceStatus,
)
from tools.media.resolve import validate_media_path
from tools.youtube.oembed_provider import OEmbedYouTubeProvider

logger = get_logger(__name__)

DEFAULT_YTDLP_FORMAT = DEFAULT_FORMAT

_SOURCE_README = """# YouTube source package

This directory stores YouTube source metadata and a local media copy downloaded
via yt-dlp for pipeline processing.

Only process content you are authorized to use, and comply with YouTube
platform terms and copyright requirements. The application uses its bundled
imageio-ffmpeg executable, or FFMPEG_PATH when explicitly configured.
"""

DownloadFn = Callable[[str, Path, dict[str, Any]], Path]


def _to_agent_error(exc: YouTubeDownloadError) -> YouTubeAgentError:
    return YouTubeAgentError(exc.message)


def _default_ytdlp_download(
    url: str,
    source_dir: Path,
    options: dict[str, Any],
) -> Path:
    """Download media with yt-dlp into ``source_dir``; return the media file path."""
    _ = options
    source_dir = Path(source_dir)
    source_dir.mkdir(parents=True, exist_ok=True)
    result = download_youtube(url, dest_dir=source_dir)
    if not result.ok or not result.local_path:
        if result.error:
            raise _to_agent_error(result.error)
        raise YouTubeAgentError("YouTube media download failed.")

    media = Path(result.local_path)
    if media.parent.resolve() != source_dir.resolve():
        dest = source_dir / media.name
        try:
            shutil.copy2(media, dest)
            media = dest
        except OSError as exc:
            raise StorageError(f"Failed to place YouTube media in source/: {exc}") from exc
    return Path(validate_media_path(media))


def download_youtube_media(url: str, dest_dir: Path | str) -> Path:
    """Public helper: download ``url`` into ``dest_dir`` and return the file path."""
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
            "format": get_settings().youtube_download_format or DEFAULT_YTDLP_FORMAT,
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
                },
            )
        except YouTubeDownloadError as exc:
            raise _to_agent_error(exc) from exc
        except YouTubeAgentError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("YouTube media download failed")
            raise YouTubeAgentError(f"YouTube media download failed: {exc}") from exc

        media_path = Path(validate_media_path(media_path))

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
