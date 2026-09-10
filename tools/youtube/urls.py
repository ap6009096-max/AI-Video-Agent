"""YouTube URL validation and normalization helpers."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

from core.errors import YouTubeAgentError

_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_INVISIBLE_RE = re.compile(r"[\u200b\u200c\u200d\ufeff\u00a0]")

_YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtu.be",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
}


def _snippet(value: str, limit: int = 80) -> str:
    text = (value or "").replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _coerce_raw_youtube_url(url: str) -> str:
    """Normalize pasted YouTube text before parsing.

    Handles missing schemes, quotes/brackets, and invisible clipboard junk.
    """
    raw = _INVISIBLE_RE.sub("", (url or "")).strip()
    if not raw:
        return ""
    if (raw.startswith('"') and raw.endswith('"')) or (
        raw.startswith("'") and raw.endswith("'")
    ):
        raw = raw[1:-1].strip()
    if raw.startswith("<") and raw.endswith(">"):
        raw = raw[1:-1].strip()
    if "://" not in raw:
        raw = f"https://{raw}"
    return raw


def extract_video_id(url: str) -> str:
    """Extract an 11-character YouTube video id from common URL formats."""
    raw = _coerce_raw_youtube_url(url)
    if not raw:
        raise YouTubeAgentError("YouTube URL is required.")

    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        raise YouTubeAgentError(
            "YouTube URL must start with http:// or https:// "
            f"(got {_snippet(raw)!r})."
        )

    host_key = (parsed.netloc or "").lower()
    if "@" in host_key:
        # userinfo@host — keep host only
        host_key = host_key.rsplit("@", 1)[-1]
    if host_key.endswith(":443") or host_key.endswith(":80"):
        host_key = host_key.rsplit(":", 1)[0]

    if (
        host_key not in _YOUTUBE_HOSTS
        and not host_key.endswith(".youtube.com")
        and not host_key.endswith(".youtube-nocookie.com")
    ):
        raise YouTubeAgentError(
            "URL must be a valid YouTube link (youtube.com or youtu.be) "
            f"(got host {_snippet(host_key or raw)!r})."
        )

    path = (parsed.path or "").strip("/")
    query = parse_qs(parsed.query or "")

    video_id = ""
    if host_key in {"youtu.be", "www.youtu.be"}:
        video_id = path.split("/")[0] if path else ""
    elif path.startswith("watch"):
        video_id = (query.get("v") or [""])[0]
    elif path.startswith("shorts/"):
        video_id = path.split("/", 1)[1].split("/")[0]
    elif path.startswith("embed/"):
        video_id = path.split("/", 1)[1].split("/")[0]
    elif path.startswith("live/"):
        video_id = path.split("/", 1)[1].split("/")[0]
    elif "v" in query:
        video_id = (query.get("v") or [""])[0]

    video_id = video_id.strip()
    if not _VIDEO_ID_RE.match(video_id):
        raise YouTubeAgentError(
            "Could not extract a valid YouTube video id from the URL "
            f"({_snippet(raw)!r})."
        )
    return video_id


def canonical_watch_url(video_id: str) -> str:
    """Return the canonical watch URL for a video id."""
    if not _VIDEO_ID_RE.match(video_id):
        raise YouTubeAgentError("Invalid YouTube video id.")
    return f"https://www.youtube.com/watch?v={video_id}"


def normalize_youtube_url(url: str) -> str:
    """Validate and normalize a YouTube URL to the canonical watch form."""
    video_id = extract_video_id(url)
    return canonical_watch_url(video_id)
