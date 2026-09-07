"""Tests for boundary-based smart clip selection."""

from __future__ import annotations

from schemas.clips import ClipCandidate
from tools.clips.select import select_smart_clips, _iou


def _timed_transcript(n: int = 20, sent_len: float = 3.0) -> dict:
    sentences = []
    for i in range(n):
        start = i * sent_len
        end = start + sent_len - 0.2
        sentences.append(
            {
                "id": f"s{i}",
                "index": i,
                "text": f"This is a complete sentence number {i} about the topic.",
                "start_seconds": start,
                "end_seconds": end,
            }
        )
    return {
        "sentences": sentences,
        "hooks": [
            {
                "sentence_id": "s0",
                "text": sentences[0]["text"],
                "reason": "opener",
                "score": 0.9,
            }
        ],
        "important_statements": [
            {
                "sentence_id": "s5",
                "text": sentences[5]["text"],
                "reason": "key",
            }
        ],
        "clip_boundaries": [{"after_sentence_id": "s4", "reason": "beat"}],
        "sections": [
            {"id": "sec1", "sentence_ids": [f"s{i}" for i in range(0, 10)]},
            {"id": "sec2", "sentence_ids": [f"s{i}" for i in range(10, 20)]},
        ],
    }


def test_required_fields_and_sentence_snap() -> None:
    transcript = _timed_transcript()
    moments = {
        "moments": [
            {
                "category": "important",
                "start": 14.0,
                "end": 16.0,
                "score": 0.85,
                "title": "Key insight",
                "reason": "important",
                "transcript": "insight",
            }
        ]
    }
    clips = select_smart_clips(
        transcript=transcript,
        moments=moments,
        target_duration=30,
        duration_tolerance=0.5,
        min_score=0.1,
    )
    assert clips
    for c in clips:
        assert c.start < c.end
        assert c.duration == c.end - c.start or abs(c.duration - (c.end - c.start)) < 1e-6
        assert c.transcript
        assert c.category
        assert c.hook is not None
        assert c.reason
        assert "score" in c.model_dump()
        # Snap: starts/ends must match sentence bounds
        starts = {s["start_seconds"] for s in transcript["sentences"]}
        ends = {s["end_seconds"] for s in transcript["sentences"]}
        assert any(abs(c.start - s) < 1e-3 for s in starts)
        assert any(abs(c.end - e) < 1e-3 for e in ends)
        assert "fixed" in c.reason.lower() or "not a fixed" in c.reason.lower()


def test_no_fixed_chunk_tiling() -> None:
    """Ensure we do not emit a regular grid of equal-length tiles."""
    transcript = _timed_transcript(n=30, sent_len=2.0)
    moments = {
        "moments": [
            {
                "category": "viral",
                "start": 5.0,
                "end": 7.0,
                "score": 0.9,
                "title": "A",
                "reason": "r",
                "transcript": "a",
            },
            {
                "category": "funny",
                "start": 40.0,
                "end": 42.0,
                "score": 0.8,
                "title": "B",
                "reason": "r",
                "transcript": "b",
            },
        ]
    }
    clips = select_smart_clips(
        transcript=transcript,
        moments=moments,
        target_duration=15,
        duration_tolerance=0.4,
        min_score=0.05,
        max_clips=10,
    )
    starts = sorted(c.start for c in clips)
    if len(starts) >= 3:
        gaps = [starts[i + 1] - starts[i] for i in range(len(starts) - 1)]
        # Fixed 15s tiling would produce nearly identical gaps
        assert not all(abs(g - 15.0) < 0.5 for g in gaps)


def test_overlap_suppression() -> None:
    a = ClipCandidate(start=0.0, end=20.0, duration=20.0, score=0.9, transcript="a", hook="a", reason="r", category="viral")
    b = ClipCandidate(start=2.0, end=22.0, duration=20.0, score=0.8, transcript="b", hook="b", reason="r", category="viral")
    assert _iou(a, b) > 0.35

    transcript = _timed_transcript(n=25, sent_len=2.5)
    moments = {
        "moments": [
            {
                "category": "viral",
                "start": 10.0,
                "end": 12.0,
                "score": 0.95,
                "title": "One",
                "reason": "r",
                "transcript": "one",
            },
            {
                "category": "viral",
                "start": 11.0,
                "end": 13.0,
                "score": 0.9,
                "title": "Two",
                "reason": "r",
                "transcript": "two",
            },
        ]
    }
    clips = select_smart_clips(
        transcript=transcript,
        moments=moments,
        target_duration=30,
        duration_tolerance=0.5,
        max_overlap=0.35,
        min_score=0.05,
    )
    for i, c1 in enumerate(clips):
        for c2 in clips[i + 1 :]:
            assert _iou(c1, c2) <= 0.35 + 1e-6


def test_target_duration_preference() -> None:
    transcript = _timed_transcript(n=40, sent_len=2.0)
    moments = {
        "moments": [
            {
                "category": "important",
                "start": 20.0,
                "end": 22.0,
                "score": 0.9,
                "title": "Insight",
                "reason": "r",
                "transcript": "insight",
            }
        ]
    }
    clips = select_smart_clips(
        transcript=transcript,
        moments=moments,
        target_duration=30,
        duration_tolerance=0.35,
        min_score=0.05,
    )
    assert clips
    # Mean duration should be near target band
    mean_d = sum(c.duration for c in clips) / len(clips)
    assert 30 * 0.5 <= mean_d <= 30 * 1.5


def test_silence_trim_keeps_sentence_bounds() -> None:
    transcript = _timed_transcript(n=15, sent_len=3.0)
    audio = {
        "silence_spans": [
            {"start": 0.0, "end": 2.5, "score": 0.9, "label": "silence"},
        ]
    }
    moments = {
        "moments": [
            {
                "category": "important",
                "start": 6.0,
                "end": 8.0,
                "score": 0.8,
                "title": "T",
                "reason": "r",
                "transcript": "t",
            }
        ]
    }
    clips = select_smart_clips(
        transcript=transcript,
        moments=moments,
        audio_analysis=audio,
        target_duration=15,
        duration_tolerance=0.6,
        min_score=0.05,
    )
    starts = {s["start_seconds"] for s in transcript["sentences"]}
    ends = {s["end_seconds"] for s in transcript["sentences"]}
    for c in clips:
        assert any(abs(c.start - s) < 1e-3 for s in starts)
        assert any(abs(c.end - e) < 1e-3 for e in ends)
