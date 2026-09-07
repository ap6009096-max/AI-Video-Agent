"""Abstract YouTube source provider interface."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from schemas.youtube import PreparedYouTubeSource, YouTubeSourceMetadata


@runtime_checkable
class YouTubeSourceProvider(Protocol):
    """Swap-friendly interface for YouTube metadata and source preparation.

    Default oEmbed provider is metadata-only. Binary media download is enabled
    only via an authorized integration (e.g. yt-dlp) when configured.
    """

    name: str

    def normalize_url(self, url: str) -> str:
        """Return a canonical YouTube watch URL."""
        ...

    def fetch_metadata(self, url: str) -> YouTubeSourceMetadata:
        """Fetch available metadata through authorized APIs only."""
        ...

    def prepare_source(
        self,
        project_dir: str | Path,
        metadata: YouTubeSourceMetadata,
    ) -> PreparedYouTubeSource:
        """Write source/ artifacts; may download media when the provider allows it."""
        ...


def get_youtube_provider() -> YouTubeSourceProvider:
    """Return oEmbed (default) or yt-dlp provider when download is enabled."""
    from config.settings import get_settings

    settings = get_settings()
    if settings.youtube_download_enabled:
        from tools.youtube.ytdlp_provider import YtdlpYouTubeProvider

        return YtdlpYouTubeProvider()

    from tools.youtube.oembed_provider import OEmbedYouTubeProvider

    return OEmbedYouTubeProvider()
