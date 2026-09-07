"""Tests for reframe crop planning — not naive center crop."""

from __future__ import annotations

from schemas.reframe import AspectPreset, FocusRoi
from tools.reframe.catalog import resolve_aspect
from tools.reframe.plan import (
    build_reframe_plan,
    build_windows_from_samples,
    center_crop_rect,
    compute_crop_rect,
)


def test_crop_follows_offset_focus() -> None:
    src_w, src_h = 1920, 1080
    target = 9 / 16
    center = center_crop_rect(src_w, src_h, target)
    left = compute_crop_rect(
        focus_x=300.0,
        focus_y=400.0,
        src_w=src_w,
        src_h=src_h,
        target_ratio=target,
        padding=0.1,
    )
    assert abs((left[2] / left[3]) - target) < 0.02
    # Left-biased focus should not match pure center crop x
    assert left[0] != center[0]


def test_windows_match_target_aspect() -> None:
    samples = [
        FocusRoi(
            kind="face",
            x=200,
            y=100,
            w=100,
            h=100,
            score=1.0,
            time_seconds=0.5,
        ),
        FocusRoi(
            kind="face",
            x=800,
            y=120,
            w=100,
            h=100,
            score=1.0,
            time_seconds=2.5,
        ),
    ]
    windows = build_windows_from_samples(
        samples,
        src_w=1920,
        src_h=1080,
        target_ratio=0.5625,
        start=0.0,
        end=4.0,
    )
    assert windows
    for w in windows:
        assert abs((w.crop_w / w.crop_h) - 0.5625) < 0.05
        assert w.method in {
            "face",
            "speaker_face",
            "object",
            "motion",
            "fallback_center",
        }


def test_build_plan_not_center_when_focus_offset() -> None:
    aspect = resolve_aspect("9:16") or AspectPreset(
        name="9:16", ratio=0.5625, output_width=1080, output_height=1920
    )
    samples = [
        FocusRoi(
            kind="face",
            x=100,
            y=200,
            w=120,
            h=120,
            score=2.0,
            time_seconds=1.0,
        )
    ]
    plan = build_reframe_plan(
        project_id="p1",
        src_w=1920,
        src_h=1080,
        duration=5.0,
        aspect=aspect,
        samples=samples,
        clips={"clips": [{"id": 1, "start": 0.0, "end": 5.0}]},
    )
    assert plan.passthrough is False
    assert plan.clip_plans
    window = plan.clip_plans[0].windows[0]
    cx, _, _, _ = center_crop_rect(1920, 1080, 0.5625)
    assert window.crop_x != cx or window.method == "face"
