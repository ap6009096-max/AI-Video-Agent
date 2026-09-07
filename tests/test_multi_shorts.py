"""Tests for multi-duration Shorts clip selection and schema."""

from __future__ import annotations

from schemas.job import ALLOWED_SHORT_DURATIONS, FeatureFlags, VideoJobConfig
from tools.clips.select import select_multi_duration_clips


def _timed_transcript(n: int = 40, sent_len: float = 3.0) -> dict:
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
                "sentence_id": "s10",
                "text": sentences[10]["text"],
                "reason": "key",
            }
        ],
        "clip_boundaries": [{"after_sentence_id": "s8", "reason": "beat"}],
        "sections": [
            {"id": "sec1", "sentence_ids": [f"s{i}" for i in range(0, 20)]},
            {"id": "sec2", "sentence_ids": [f"s{i}" for i in range(20, 40)]},
        ],
    }


def test_short_durations_include_10_and_40() -> None:
    assert 10 in ALLOWED_SHORT_DURATIONS
    assert 40 in ALLOWED_SHORT_DURATIONS
    cfg = VideoJobConfig()
    assert cfg.short_durations == [10, 40, 90]
    assert FeatureFlags().multi_shorts_export is False


def test_multi_duration_tags_target_duration() -> None:
    transcript = _timed_transcript()
    moments = {
        "moments": [
            {
                "category": "important",
                "start": 8.0,
                "end": 12.0,
                "score": 0.9,
                "title": "Insight A",
                "reason": "important",
                "transcript": "insight",
            },
            {
                "category": "viral",
                "start": 50.0,
                "end": 55.0,
                "score": 0.85,
                "title": "Insight B",
                "reason": "viral",
                "transcript": "hook",
            },
            {
                "category": "funny",
                "start": 90.0,
                "end": 95.0,
                "score": 0.8,
                "title": "Insight C",
                "reason": "funny",
                "transcript": "laugh",
            },
        ]
    }
    clips = select_multi_duration_clips(
        transcript=transcript,
        moments=moments,
        short_durations=[10, 40, 90],
        duration_tolerance=0.5,
        min_score=0.05,
        max_per_duration=2,
        max_overlap=0.5,
    )
    assert clips
    targets = {int(c.target_duration) for c in clips if c.target_duration}
    assert targets & {10, 40, 90}
    for c in clips:
        assert c.target_duration > 0
        assert "multi_duration" in (c.source_signals or []) or any(
            "target_duration" in e for e in c.evidence
        )
        assert c.start < c.end
