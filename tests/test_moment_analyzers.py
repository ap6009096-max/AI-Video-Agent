"""Tests for moment analyzers and registry filtering."""

from __future__ import annotations

from schemas.moments import DetectedMoment
from tools.moments.analyzers import analyze_funny, analyze_important
from tools.moments.context import (
    AudioHit,
    MomentContext,
    SpeechUnit,
    build_moment_context,
)
from tools.moments.postprocess import postprocess_moments
from tools.moments.registry import enabled_categories_from_features, run_moment_analyzers
from schemas.job import FeatureFlags


def test_funny_from_laughter_with_context() -> None:
    ctx = MomentContext(
        units=[SpeechUnit(0.0, 1.0, "that was hilarious haha")],
        audio_hits=[
            AudioHit(0.0, 1.0, 0.8, "laughter", ["funny", "reaction"], "keyword"),
            AudioHit(1.0, 1.5, 0.6, "reaction", ["reaction"], "burst"),
        ],
    )
    moments = analyze_funny(ctx)
    assert moments
    assert moments[0].category == "funny"
    assert moments[0].evidence
    assert moments[0].score >= 0.8


def test_important_from_hooks() -> None:
    ctx = MomentContext(
        units=[
            SpeechUnit(0.0, 2.0, "This changes everything."),
            SpeechUnit(3.0, 4.0, "Moving on."),
        ],
        hooks=[{"sentence_index": 0, "reason": "opener", "score": 0.9}],
        speaker_changes=[(2.0, 2.5, 0.5)],
        audio_hits=[
            AudioHit(1.8, 2.2, 0.5, "pause", ["clip_boundary"], "gap"),
        ],
    )
    moments = analyze_important(ctx)
    assert moments
    assert moments[0].category == "important"
    assert "transcript:important_or_hook" in moments[0].evidence


def test_enabled_filter_only_funny() -> None:
    flags = FeatureFlags(
        smart_clip_detection=True,
        funny_moments=True,
        viral_moments=False,
        important_moments=False,
    )
    enabled = enabled_categories_from_features(flags)
    assert enabled == ["funny"]

    moments = run_moment_analyzers(
        enabled=enabled,
        speech_transcript={
            "segments": [
                {"start": 0.0, "end": 1.0, "text": "lol haha"},
                {"start": 2.0, "end": 3.0, "text": "What is this?"},
            ]
        },
        audio_analysis={
            "laughter_candidates": [
                {
                    "start": 0.0,
                    "end": 1.0,
                    "score": 0.9,
                    "label": "laughter",
                    "evidence_tags": ["funny", "reaction"],
                    "detail": "x",
                }
            ],
            "question_spans": [
                {
                    "start": 2.0,
                    "end": 3.0,
                    "score": 0.8,
                    "label": "question",
                    "evidence_tags": ["clip_boundary"],
                }
            ],
        },
    )
    assert moments
    assert all(m.category == "funny" for m in moments)


def test_postprocess_cap_and_merge() -> None:
    raw = [
        DetectedMoment(
            category="viral",
            start=0.0,
            end=1.0,
            score=0.9,
            title="a",
            reason="r",
            transcript="a",
            evidence=["e1"],
        ),
        DetectedMoment(
            category="viral",
            start=0.5,
            end=2.0,
            score=0.8,
            title="b",
            reason="r",
            transcript="b",
            evidence=["e2"],
        ),
        DetectedMoment(
            category="viral",
            start=10.0,
            end=11.0,
            score=0.2,
            title="low",
            reason="r",
            transcript="low",
            evidence=[],
        ),
    ]
    out = postprocess_moments(raw, min_score=0.35, max_per_category=5, merge_gap=0.75)
    assert all(m.score >= 0.35 for m in out)
    assert len(out) == 1  # merged overlapping
    assert "e1" in out[0].evidence and "e2" in out[0].evidence


def test_build_context_from_dicts() -> None:
    ctx = build_moment_context(
        speech_transcript={"segments": [{"start": 0.0, "end": 1.0, "text": "hi"}]},
        scenes={
            "scenes": [
                {
                    "start": 0.0,
                    "end": 2.0,
                    "visual_change_score": 0.5,
                    "change_kinds": ["cut"],
                }
            ]
        },
        analysis={"properties": {"duration_seconds": 5.0}},
    )
    assert ctx.duration == 5.0
    assert ctx.units and ctx.scenes
