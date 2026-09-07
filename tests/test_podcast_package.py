"""Tests for podcast clip packaging."""

from __future__ import annotations

from tools.podcast.package import (
    detect_source_media,
    is_podcast_video_type,
    package_podcast_clips,
    _iou,
)


def test_is_podcast_video_type() -> None:
    assert is_podcast_video_type("Podcast")
    assert is_podcast_video_type("Interview")
    assert is_podcast_video_type("podcast clip")
    assert not is_podcast_video_type("Shorts")


def test_detect_source_media_audio_extension() -> None:
    assert detect_source_media(upload_path=r"C:\tmp\ep.mp3") == "audio"
    assert detect_source_media(upload_path=r"C:\tmp\ep.mp4") == "video"


def test_package_maps_kinds_and_platforms() -> None:
    moments = {
        "moments": [
            {
                "category": "quote",
                "start": 1.0,
                "end": 8.0,
                "score": 0.8,
                "title": "Best line",
                "reason": "quote",
                "transcript": "This changes everything.",
            },
            {
                "category": "important",
                "start": 20.0,
                "end": 35.0,
                "score": 0.75,
                "title": "Lesson",
                "reason": "key",
                "transcript": "Always measure twice.",
            },
        ]
    }
    funny = {
        "moments": [
            {
                "start": 40.0,
                "end": 50.0,
                "humor_score": 0.7,
                "suggested_title": "Joke",
                "explanation": "punch",
                "transcript": "Why did the chicken?",
            }
        ]
    }
    viral = {
        "moments": [
            {
                "start": 60.0,
                "end": 75.0,
                "final_score": 0.85,
                "suggested_title": "Hot take",
                "explanation": "viral",
                "transcript": "Nobody talks about this.",
            }
        ]
    }
    clips = package_podcast_clips(
        moments=moments,
        funny_moments=funny,
        viral_moments=viral,
        min_score=0.2,
        max_clips=20,
    )
    assert clips
    kinds = {c.kind for c in clips}
    assert "quote" in kinds
    assert "lesson" in kinds
    assert "funny" in kinds
    assert "viral" in kinds
    for c in clips:
        assert c.platforms
        assert c.score >= 0.2
        assert c.start < c.end
        if c.kind == "funny":
            assert "tiktok" in c.platforms or "reels" in c.platforms
        if c.kind == "quote":
            assert "quotes" in c.platforms


def test_overlap_cap() -> None:
    moments = {
        "moments": [
            {
                "category": "viral",
                "start": 10.0,
                "end": 40.0,
                "score": 0.9,
                "title": "A",
                "reason": "r",
                "transcript": "a",
            },
            {
                "category": "viral",
                "start": 12.0,
                "end": 42.0,
                "score": 0.85,
                "title": "B",
                "reason": "r",
                "transcript": "b",
            },
        ]
    }
    clips = package_podcast_clips(moments=moments, min_score=0.1, max_overlap=0.35)
    for i, c1 in enumerate(clips):
        for c2 in clips[i + 1 :]:
            assert _iou(c1, c2) <= 0.35 + 1e-6


def test_empty_when_no_seeds() -> None:
    assert package_podcast_clips() == []
