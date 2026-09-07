"""Tests for multi-signal funny moment detection."""

from __future__ import annotations

from tools.moments.context import AudioHit, MomentContext, SpeechUnit
from tools.moments.funny_detect import (
    detect_funny_moments,
    merge_funny_moments_into_detected,
)
from tools.moments.registry import run_moment_analyzers
from schemas.funny import FunnyMoment


def test_laughter_alone_rejected() -> None:
    ctx = MomentContext(
        units=[SpeechUnit(0.0, 1.0, "okay then")],
        audio_hits=[
            AudioHit(0.0, 1.0, 0.95, "laughter", ["funny"], "crowd laugh"),
        ],
    )
    moments = detect_funny_moments(context=ctx, min_score=0.1)
    assert moments == []


def test_setup_punchline_pause_accepted() -> None:
    ctx = MomentContext(
        units=[
            SpeechUnit(0.0, 2.0, "Why did the chicken cross the road"),
            SpeechUnit(2.8, 4.0, "To get to the other side!"),
        ],
        audio_hits=[
            AudioHit(2.0, 2.6, 0.7, "pause", ["clip_boundary"], "gap"),
        ],
    )
    moments = detect_funny_moments(context=ctx, min_score=0.4)
    assert moments
    assert moments[0].category == "funny"
    assert moments[0].humor_score >= 0.4
    assert moments[0].suggested_title
    assert moments[0].explanation
    assert "punchline" in moments[0].humor_kinds or "joke" in moments[0].humor_kinds
    assert moments[0].evidence


def test_sarcasm_plus_reaction() -> None:
    ctx = MomentContext(
        units=[SpeechUnit(1.0, 2.5, "Yeah right, that will totally work.")],
        audio_hits=[
            AudioHit(2.0, 2.8, 0.8, "reaction", ["reaction"], "gasp"),
        ],
    )
    moments = detect_funny_moments(context=ctx, min_score=0.35)
    assert moments
    assert "sarcasm" in moments[0].humor_kinds
    assert any("reaction" in e or "sarcasm" in e for e in moments[0].evidence)


def test_max_moments_cap() -> None:
    units = []
    for i in range(20):
        t = float(i * 3)
        units.append(SpeechUnit(t, t + 1.0, "Why did the chicken cross the road"))
        units.append(
            SpeechUnit(t + 1.5, t + 2.5, f"Punchline number {i}!")
        )
    ctx = MomentContext(
        units=units,
        audio_hits=[
            AudioHit(t + 1.0, t + 1.4, 0.6, "pause", [], "")
            for t in (float(i * 3) for i in range(20))
        ],
    )
    moments = detect_funny_moments(context=ctx, max_moments=3, min_score=0.3)
    assert len(moments) <= 3


def test_merge_into_detected() -> None:
    fm = FunnyMoment(
        id=0,
        start=1.0,
        end=3.0,
        humor_kinds=["joke", "punchline"],
        humor_score=0.72,
        explanation="signals=transcript,timing",
        transcript="To get to the other side!",
        suggested_title="Chicken punchline",
        evidence=["transcript:joke_setup@0.0"],
    )
    merged = merge_funny_moments_into_detected([fm])
    assert len(merged) == 1
    assert merged[0].category == "funny"
    assert merged[0].score == 0.72
    assert merged[0].title == "Chicken punchline"
    assert merged[0].reason == "signals=transcript,timing"


def test_registry_uses_funny_moments_when_provided() -> None:
    report = {
        "moments": [
            {
                "id": 0,
                "start": 0.0,
                "end": 2.0,
                "category": "funny",
                "humor_kinds": ["meme_worthy"],
                "humor_score": 0.66,
                "explanation": "from dedicated agent",
                "transcript": "no cap bruh",
                "suggested_title": "Meme line",
                "evidence": ["transcript:meme@0.0", "timing:punch_after_gap@0.0"],
            }
        ]
    }
    moments = run_moment_analyzers(
        enabled=["funny"],
        speech_transcript={
            "segments": [{"start": 0.0, "end": 1.0, "text": "lol haha"}]
        },
        audio_analysis={
            "laughter_candidates": [
                {
                    "start": 0.0,
                    "end": 1.0,
                    "score": 0.99,
                    "label": "laughter",
                    "evidence_tags": ["funny"],
                }
            ]
        },
        funny_moments=report,
    )
    assert len(moments) == 1
    assert moments[0].title == "Meme line"
    assert moments[0].score == 0.66
    assert moments[0].reason == "from dedicated agent"
