"""Tests for pipeline step definitions."""

from __future__ import annotations

from schemas.job import PIPELINE_STEPS, initial_progress_steps


EXPECTED_LABELS = [
    "Source detected",
    "Video loaded",
    "Transcript extracted",
    "Scenes detected",
    "Audio analyzed",
    "Important moments found",
    "Funny moments found",
    "Viral moments found",
    "Clips selected",
    "Story generated",
    "Localization completed",
    "Captions generated",
    "Video rendered",
    "Quality checked",
    "Export completed",
]


def test_pipeline_steps_count_and_labels() -> None:
    assert len(PIPELINE_STEPS) == 15
    assert list(PIPELINE_STEPS) == EXPECTED_LABELS


def test_initial_progress_steps() -> None:
    steps = initial_progress_steps()
    assert len(steps) == 15
    assert steps[0]["label"] == "Source detected"
    assert steps[-1]["label"] == "Export completed"
    assert all(s["status"] == "pending" for s in steps)
