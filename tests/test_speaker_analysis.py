"""Tests for speaker turn heuristics."""

from __future__ import annotations

from tools.audio.speaker_analysis import analyze_speakers


def test_turn_gaps_create_changes() -> None:
    result = analyze_speakers(
        speech_transcript={
            "segments": [
                {"start": 0.0, "end": 1.0, "text": "First turn"},
                {"start": 3.0, "end": 4.0, "text": "Second turn"},
                {"start": 4.2, "end": 5.0, "text": "ok"},
            ]
        },
        turn_gap=0.8,
    )
    assert len(result["turns"]) >= 2
    assert result["speaker_change_candidates"]
    assert result["conversational_structure"].turn_taking >= 0.0
    assert "speaker_change_rate" in result["summary_scores"]


def test_structure_scores_present() -> None:
    result = analyze_speakers(
        transcript={
            "sentences": [
                {"start_seconds": 0.0, "end_seconds": 5.0, "text": "Long monologue here"},
                {"start_seconds": 6.0, "end_seconds": 6.5, "text": "yeah"},
            ]
        },
        turn_gap=0.8,
    )
    struct = result["conversational_structure"]
    assert 0.0 <= struct.monologue_ratio <= 1.0
    assert 0.0 <= struct.backchannel_density <= 1.0
