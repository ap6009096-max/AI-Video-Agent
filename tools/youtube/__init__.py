"""YouTube tool integrations (abstract provider + URL helpers).

Submodules load lazily so importing ``tools.youtube.urls`` alone does not
pull yt-dlp / ingestion download stacks at Streamlit boot.
"""

from __future__ import annotations

from typing import Any

from tools.youtube.urls import canonical_watch_url, extract_video_id, normalize_youtube_url

__all__ = [
    "OEmbedYouTubeProvider",
    "YtdlpYouTubeProvider",
    "YouTubeSourceProvider",
    "canonical_watch_url",
    "extract_video_id",
    "get_youtube_provider",
    "normalize_youtube_url",
    "parse_iso8601_duration",
]

_LAZY_ATTRS: dict[str, tuple[str, str]] = {
    "OEmbedYouTubeProvider": (
        "tools.youtube.oembed_provider",
        "OEmbedYouTubeProvider",
    ),
    "parse_iso8601_duration": (
        "tools.youtube.oembed_provider",
        "parse_iso8601_duration",
    ),
    "YouTubeSourceProvider": ("tools.youtube.provider", "YouTubeSourceProvider"),
    "get_youtube_provider": ("tools.youtube.provider", "get_youtube_provider"),
    "YtdlpYouTubeProvider": (
        "tools.youtube.ytdlp_provider",
        "YtdlpYouTubeProvider",
    ),
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
