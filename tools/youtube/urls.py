"""YouTube URL validation and normalization helpers."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

from core.errors import YouTubeAgentError

_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

_YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtu.be",
}


def extract_video_id(url: str) -> str:
    """Extract an 11-character YouTube video id from common URL formats."""
    raw = (url or "").strip()
    if not raw:
        raise YouTubeAgentError("YouTube URL is required.")

    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        raise YouTubeAgentError("YouTube URL must start with http:// or https://.")

    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host_key = host
    else:
        host_key = host

    if host_key not in _YOUTUBE_HOSTS and not host_key.endswith(".youtube.com"):
        raise YouTubeAgentError(
            "URL must be a valid YouTube link (youtube.com or youtu.be)."
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
        raise YouTubeAgentError("Could not extract a valid YouTube video id from the URL.")
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
