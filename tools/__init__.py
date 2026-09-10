"""Tool integrations (FFmpeg, OpenCV, Whisper, YouTube, HTTP, etc.).

Keep package init free of eager YouTube/provider imports so Streamlit boot
(e.g. ``tools.scripts.ingest``) does not load yt-dlp/ingestion stacks.
"""

from __future__ import annotations

from typing import Any

__all__ = ["get_youtube_provider", "normalize_youtube_url"]

_LAZY_ATTRS: dict[str, tuple[str, str]] = {
    "get_youtube_provider": ("tools.youtube.provider", "get_youtube_provider"),
    "normalize_youtube_url": ("tools.youtube.urls", "normalize_youtube_url"),
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
