"""Tests for YouTube URL helpers."""

from __future__ import annotations

import pytest

from core.errors import YouTubeAgentError
from tools.youtube.urls import extract_video_id, normalize_youtube_url


VIDEO_ID = "dQw4w9WgXcQ"


@pytest.mark.parametrize(
    "url",
    [
        f"https://www.youtube.com/watch?v={VIDEO_ID}",
        f"https://youtu.be/{VIDEO_ID}",
        f"https://www.youtube.com/shorts/{VIDEO_ID}",
        f"https://www.youtube.com/embed/{VIDEO_ID}",
        f"https://m.youtube.com/watch?v={VIDEO_ID}",
        f"https://www.youtube.com/live/{VIDEO_ID}",
        f"https://youtube.com/watch?v={VIDEO_ID}&t=30",
        f"www.youtube.com/watch?v={VIDEO_ID}",
        f"youtu.be/{VIDEO_ID}",
        f'"https://www.youtube.com/watch?v={VIDEO_ID}"',
        f"<https://youtu.be/{VIDEO_ID}>",
        f"https://www.youtube-nocookie.com/embed/{VIDEO_ID}",
        f"\u200bhttps://www.youtube.com/watch?v={VIDEO_ID}\u200b",
    ],
)
def test_extract_and_normalize_common_formats(url: str) -> None:
    assert extract_video_id(url) == VIDEO_ID
    assert normalize_youtube_url(url) == f"https://www.youtube.com/watch?v={VIDEO_ID}"


def test_rejects_non_youtube_host() -> None:
    with pytest.raises(YouTubeAgentError, match="YouTube"):
        extract_video_id("https://example.com/watch?v=dQw4w9WgXcQ")


def test_rejects_missing_video_id() -> None:
    with pytest.raises(YouTubeAgentError, match="video id"):
        extract_video_id("https://www.youtube.com/watch")


def test_rejects_empty() -> None:
    with pytest.raises(YouTubeAgentError, match="required"):
        extract_video_id("")
