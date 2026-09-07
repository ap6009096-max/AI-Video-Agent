"""Default YouTube provider using oEmbed (+ optional Data API for duration)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import httpx

from config.settings import get_settings
from core.errors import StorageError, YouTubeAgentError
from core.logging import get_logger
from schemas.youtube import (
    PreparedYouTubeSource,
    YouTubeSourceMetadata,
    YouTubeSourceStatus,
)
from tools.youtube.urls import extract_video_id, normalize_youtube_url

logger = get_logger(__name__)

_OEMBED_URL = "https://www.youtube.com/oembed"
_DATA_API_URL = "https://www.googleapis.com/youtube/v3/videos"
_ISO8601_DURATION = re.compile(
    r"^P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$"
)

_SOURCE_README = """# YouTube source package

This directory stores YouTube source metadata for pipeline processing.

Local media binaries are NOT downloaded by the default provider.
Only process content you are authorized to use, and comply with YouTube
platform terms and copyright requirements.

An authorized downloader/API provider can be plugged in later without
changing the LangGraph workflow.
"""


def parse_iso8601_duration(value: str) -> float | None:
    """Parse a YouTube Data API ISO-8601 duration into seconds."""
    if not value:
        return None
    match = _ISO8601_DURATION.match(value)
    if not match:
        return None
    days = int(match.group("days") or 0)
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    return float(days * 86400 + hours * 3600 + minutes * 60 + seconds)


class OEmbedYouTubeProvider:
    """Authorized metadata via YouTube oEmbed; optional Data API for duration."""

    name = "oembed"

    def __init__(self, client: httpx.Client | None = None, timeout: float = 15.0) -> None:
        self._client = client
        self._timeout = timeout

    def normalize_url(self, url: str) -> str:
        return normalize_youtube_url(url)

    def fetch_metadata(self, url: str) -> YouTubeSourceMetadata:
        canonical = self.normalize_url(url)
        video_id = extract_video_id(canonical)

        try:
            oembed = self._fetch_oembed(canonical)
        except YouTubeAgentError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise YouTubeAgentError(f"Failed to fetch YouTube metadata: {exc}") from exc

        title = str(oembed.get("title") or "").strip()
        channel = str(oembed.get("author_name") or "").strip()
        if not title and not channel:
            raise YouTubeAgentError(
                "YouTube metadata unavailable for this URL "
                "(video may be private, restricted, or removed)."
            )

        duration = self._fetch_duration_seconds(video_id)
        notes_parts = [
            "Local media not downloaded; awaiting an authorized media provider.",
            "Only process content you are authorized to use.",
        ]
        if duration is None:
            notes_parts.append(
                "Duration unavailable without YOUTUBE_API_KEY (Data API)."
            )

        status = YouTubeSourceStatus.METADATA_READY
        return YouTubeSourceMetadata(
            url=url.strip(),
            canonical_url=canonical,
            video_id=video_id,
            title=title,
            channel=channel,
            duration_seconds=duration,
            source_status=status,
            provider=self.name,
            notes=" ".join(notes_parts),
        )

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

        prepared_meta = metadata.model_copy(
            update={
                "source_status": YouTubeSourceStatus.AWAITING_AUTHORIZED_MEDIA,
                "notes": (
                    f"{metadata.notes} "
                    "Status awaiting_authorized_media (no local binary); "
                    "transcription requires an upload or authorized media provider."
                ).strip(),
            }
        )
        meta_path = source_dir / "source_metadata.json"
        try:
            meta_path.write_text(
                json.dumps(prepared_meta.model_dump(mode="json"), indent=2),
                encoding="utf-8",
            )
            (source_dir / "README.md").write_text(_SOURCE_README, encoding="utf-8")
        except OSError as exc:
            raise StorageError(f"Failed to write source metadata: {meta_path}") from exc

        logger.info(
            "Prepared YouTube source dir=%s video_id=%s status=%s",
            source_dir,
            prepared_meta.video_id,
            prepared_meta.source_status.value,
        )
        return PreparedYouTubeSource(
            source_dir=str(source_dir.resolve()),
            metadata_path=str(meta_path.resolve()),
            local_media_path=None,
            metadata=prepared_meta,
        )

    def _get_client(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        return httpx.Client(timeout=self._timeout, follow_redirects=True)

    def _fetch_oembed(self, canonical_url: str) -> dict:
        client = self._get_client()
        owns_client = self._client is None
        try:
            response = client.get(
                _OEMBED_URL,
                params={"url": canonical_url, "format": "json"},
            )
            if response.status_code == 401 or response.status_code == 403:
                raise YouTubeAgentError(
                    "YouTube refused metadata access for this URL "
                    "(restricted or unauthorized)."
                )
            if response.status_code == 404:
                raise YouTubeAgentError(
                    "YouTube video not found or unavailable for oEmbed metadata."
                )
            if response.status_code >= 400:
                raise YouTubeAgentError(
                    f"YouTube oEmbed request failed with HTTP {response.status_code}."
                )
            data = response.json()
            if not isinstance(data, dict):
                raise YouTubeAgentError("Unexpected oEmbed response payload.")
            return data
        except httpx.HTTPError as exc:
            raise YouTubeAgentError(f"YouTube oEmbed network error: {exc}") from exc
        finally:
            if owns_client:
                client.close()

    def _fetch_duration_seconds(self, video_id: str) -> float | None:
        settings = get_settings()
        if not settings.has_youtube_api_key:
            return None
        client = self._get_client()
        owns_client = self._client is None
        try:
            response = client.get(
                _DATA_API_URL,
                params={
                    "part": "contentDetails",
                    "id": video_id,
                    "key": settings.youtube_api_key.strip(),
                },
            )
            if response.status_code >= 400:
                logger.warning(
                    "YouTube Data API duration lookup failed HTTP %s",
                    response.status_code,
                )
                return None
            payload = response.json()
            items = payload.get("items") or []
            if not items:
                return None
            raw = (items[0].get("contentDetails") or {}).get("duration") or ""
            return parse_iso8601_duration(raw)
        except Exception as exc:  # noqa: BLE001
            logger.warning("YouTube Data API duration lookup error: %s", exc)
            return None
        finally:
            if owns_client:
                client.close()
