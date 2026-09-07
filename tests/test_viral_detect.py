"""Tests for multi-dimension viral moment ranking."""

from __future__ import annotations

from schemas.funny import FunnyMoment
from schemas.viral import ViralScoreBreakdown
from tools.moments.context import AudioHit, MomentContext, SceneHit, SpeechUnit
from tools.moments.registry import run_moment_analyzers
from tools.moments.viral_detect import (
    DISCLAIMER,
    WEIGHTS,
    compute_final_score,
    detect_viral_moments,
    merge_viral_moments_into_detected,
)


def test_final_score_weights() -> None:
    scores = ViralScoreBreakdown(
        hook=1.0,
        information=1.0,
        emotion=1.0,
        humor=1.0,
        visual=1.0,
        completeness=1.0,
        shareability=1.0,
    )
    assert abs(compute_final_score(scores) - 1.0) < 1e-6
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9
    partial = ViralScoreBreakdown(hook=1.0)
    assert abs(compute_final_score(partial) - 0.20) < 1e-6


def test_ranking_order_and_reasons() -> None:
    ctx = MomentContext(
        units=[
            SpeechUnit(0.0, 2.0, "Why does this matter so much for everyone?"),
            SpeechUnit(3.0, 5.0, "Here is the key insight you need to know today."),
            SpeechUnit(8.0, 10.0, "bruh that was wild no cap"),
        ],
        hooks=[{"sentence_index": 0, "reason": "opener", "score": 0.9}],
        important=[{"sentence_index": 1, "reason": "insight", "score": 0.85}],
        audio_hits=[
            AudioHit(8.0, 9.5, 0.9, "excitement", ["viral", "reaction"], "caps"),
            AudioHit(2.5, 2.9, 0.6, "pause", ["clip_boundary"], "gap"),
        ],
        scenes=[
            SceneHit(7.5, 9.0, 0.7, ["cut", "event"], "hard cut"),
        ],
        speaker_changes=[(2.9, 3.1, 0.5)],
    )
    moments = detect_viral_moments(context=ctx, min_score=0.2, max_moments=10)
    assert moments
    assert moments[0].rank == 1
    assert all(moments[i].final_score >= moments[i + 1].final_score for i in range(len(moments) - 1))
    top = moments[0]
    assert top.scores.reasons
    for key in WEIGHTS:
        assert key in top.scores.reasons
    assert "guarantee" in top.explanation.lower() or "heuristic" in top.explanation.lower()
    assert DISCLAIMER.split("—")[0].strip().split()[0] in top.explanation or "heuristic" in top.explanation.lower()


def test_humor_uses_funny_report() -> None:
    ctx = MomentContext(
        units=[SpeechUnit(1.0, 3.0, "To get to the other side!")],
        audio_hits=[
            AudioHit(1.0, 2.5, 0.8, "speech_intensity", ["viral"], "loud"),
        ],
    )
    funny = [
        FunnyMoment(
            start=1.0,
            end=3.0,
            humor_score=0.88,
            explanation="setup+punch",
            transcript="To get to the other side!",
            suggested_title="Punch",
            evidence=["e"],
            humor_kinds=["punchline"],
        )
    ]
    moments = detect_viral_moments(
        context=ctx, funny_moments=funny, min_score=0.2
    )
    assert moments
    assert moments[0].scores.humor >= 0.8
    assert any("funny:humor_score" in e for e in moments[0].evidence)


def test_max_moments_cap() -> None:
    units = [
        SpeechUnit(float(i * 5), float(i * 5 + 2), f"What if idea number {i} changes everything?")
        for i in range(15)
    ]
    ctx = MomentContext(
        units=units,
        hooks=[{"sentence_index": i, "score": 0.9} for i in range(15)],
        audio_hits=[
            AudioHit(float(i * 5), float(i * 5 + 1), 0.85, "excitement", ["viral"], "x")
            for i in range(15)
        ],
    )
    moments = detect_viral_moments(context=ctx, max_moments=3, min_score=0.2)
    assert len(moments) <= 3
    assert [m.rank for m in moments] == list(range(1, len(moments) + 1))


def test_merge_into_detected() -> None:
    from schemas.viral import ViralMoment

    vm = ViralMoment(
        start=1.0,
        end=4.0,
        scores=ViralScoreBreakdown(hook=0.8, emotion=0.7, reasons={"hook": "h"}),
        final_score=0.55,
        rank=1,
        explanation=DISCLAIMER,
        transcript="hook line",
        suggested_title="Hook",
        evidence=["e"],
    )
    merged = merge_viral_moments_into_detected([vm])
    assert merged[0].category == "viral"
    assert merged[0].score == 0.55
    assert merged[0].title == "Hook"


def test_registry_uses_viral_moments_when_provided() -> None:
    report = {
        "moments": [
            {
                "id": 0,
                "start": 0.0,
                "end": 2.0,
                "category": "viral",
                "scores": {
                    "hook": 0.9,
                    "information": 0.5,
                    "emotion": 0.8,
                    "humor": 0.2,
                    "visual": 0.4,
                    "completeness": 0.6,
                    "shareability": 0.7,
                    "reasons": {"hook": "hook=0.90"},
                },
                "final_score": 0.61,
                "rank": 1,
                "explanation": DISCLAIMER,
                "transcript": "wow",
                "suggested_title": "Dedicated viral",
                "evidence": ["seed:audio"],
            }
        ]
    }
    moments = run_moment_analyzers(
        enabled=["viral"],
        speech_transcript={
            "segments": [{"start": 0.0, "end": 1.0, "text": "noise"}]
        },
        audio_analysis={
            "excitement_candidates": [
                {
                    "start": 0.0,
                    "end": 1.0,
                    "score": 0.99,
                    "label": "excitement",
                    "evidence_tags": ["viral"],
                }
            ]
        },
        viral_moments=report,
    )
    assert len(moments) == 1
    assert moments[0].title == "Dedicated viral"
    assert moments[0].score == 0.61
