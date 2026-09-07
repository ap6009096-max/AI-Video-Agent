"""Tests for audio signal analysis heuristics."""

from __future__ import annotations

from tools.audio.signal_analysis import analyze_audio_signals


def test_pause_and_question_detection() -> None:
    result = analyze_audio_signals(
        analysis={"properties": {"duration_seconds": 20.0}, "audio": {"silence_ranges": []}},
        speech_transcript={
            "segments": [
                {"start": 0.0, "end": 1.0, "text": "Hello there"},
                {"start": 2.5, "end": 3.5, "text": "What is going on?"},
            ]
        },
        pause_gap=0.6,
        max_events=50,
    )
    assert result["pause_spans"]
    assert result["question_spans"]
    assert "clip_boundary" in result["question_spans"][0].evidence_tags
    assert "question_density" in result["summary_scores"]


def test_laughter_keyword_and_evidence_tags() -> None:
    result = analyze_audio_signals(
        speech_transcript={
            "segments": [
                {"start": 0.0, "end": 1.0, "text": "That was hilarious haha"},
            ]
        },
        analysis={"properties": {"duration_seconds": 5.0}},
    )
    assert result["laughter_candidates"]
    tags = set(result["laughter_candidates"][0].evidence_tags)
    assert "funny" in tags
    assert "reaction" in tags


def test_max_events_cap() -> None:
    segs = [
        {"start": float(i), "end": float(i) + 0.4, "text": f"What about {i}?"}
        for i in range(0, 80)
    ]
    result = analyze_audio_signals(
        speech_transcript={"segments": segs},
        analysis={"properties": {"duration_seconds": 100.0}},
        max_events=10,
    )
    assert len(result["question_spans"]) <= 10


def test_silence_from_analysis() -> None:
    result = analyze_audio_signals(
        analysis={
            "properties": {"duration_seconds": 10.0},
            "audio": {
                "mean_volume_db": -20.0,
                "silence_ranges": [{"start": 2.0, "end": 3.5}],
            },
        },
        speech_transcript={"segments": [{"start": 0.0, "end": 1.5, "text": "Hi"}]},
    )
    assert result["silence_spans"]
    assert result["summary_scores"]["silence_ratio"] > 0
