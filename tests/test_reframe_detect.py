"""Tests for reframe focus scoring."""

from __future__ import annotations

from tools.reframe.detect import score_face_rois


def test_face_preferred_over_small_face() -> None:
    rois = score_face_rois(
        [(100, 100, 80, 80), (400, 100, 40, 40)],
        frame_w=1280,
        frame_h=720,
        time_seconds=1.0,
        speaker_active=False,
        motion_pts=[],
        speaker_boost=1.75,
        motion_boost=1.25,
    )
    assert rois
    assert rois[0].w == 80
    assert rois[0].kind == "face"


def test_speaker_boost_raises_score() -> None:
    base = score_face_rois(
        [(100, 100, 60, 60)],
        frame_w=1280,
        frame_h=720,
        time_seconds=1.0,
        speaker_active=False,
        motion_pts=[],
        speaker_boost=1.75,
        motion_boost=1.25,
    )
    boosted = score_face_rois(
        [(100, 100, 60, 60)],
        frame_w=1280,
        frame_h=720,
        time_seconds=1.0,
        speaker_active=True,
        motion_pts=[],
        speaker_boost=1.75,
        motion_boost=1.25,
    )
    assert boosted[0].score > base[0].score
    assert boosted[0].kind == "speaker_face"


def test_motion_proximity_boosts() -> None:
    far = score_face_rois(
        [(100, 100, 50, 50)],
        frame_w=1000,
        frame_h=1000,
        time_seconds=0.5,
        speaker_active=False,
        motion_pts=[(0.9, 0.9, 1.0)],
        speaker_boost=1.75,
        motion_boost=1.25,
    )
    near = score_face_rois(
        [(100, 100, 50, 50)],
        frame_w=1000,
        frame_h=1000,
        time_seconds=0.5,
        speaker_active=False,
        motion_pts=[(0.125, 0.125, 1.0)],
        speaker_boost=1.75,
        motion_boost=1.25,
    )
    assert near[0].score > far[0].score
