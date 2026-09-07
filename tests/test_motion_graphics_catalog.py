"""Tests for motion graphics catalog."""

from __future__ import annotations

from schemas.job import VideoJobConfig
from schemas.motion_graphics import GeminiMotionGraphicsBatch, MotionOverlay
from tools.motion_graphics.catalog import (
    build_motion_graphics_pack,
    clear_motion_graphics_cache,
)

_VALID = {
    "kinetic_typography",
    "animated_title",
    "lower_third",
    "data_visualization",
    "chart",
    "statistic",
    "educational_overlay",
}


def test_flag_off_skips() -> None:
    clear_motion_graphics_cache()
    pack = build_motion_graphics_pack(enabled=False)
    assert pack.plan.skipped is True
    assert pack.plan.overlays == []
    assert pack.plan.provider == "none"


def test_heuristic_overlays_supported_kinds() -> None:
    clear_motion_graphics_cache()
    pack = build_motion_graphics_pack(
        enabled=True,
        config=VideoJobConfig(visual_style="Cinematic", video_type="Explainer"),
        script_pack={
            "primary": {
                "title": "Growth Tips",
                "hook": "Up 40%",
                "script": "Sales hit 40%. Tip: start small.",
            }
        },
        storyboard_pack={
            "plan": {
                "skipped": False,
                "shots": [
                    {"scene": 1, "visual": "Open", "voiceover": "Go big"},
                    {"scene": 2, "visual": "Chart", "voiceover": "See the lift"},
                ],
            }
        },
        character_pack={
            "plan": {
                "skipped": False,
                "characters": [{"name": "Alex", "role_type": "human"}],
            }
        },
        analyze_fn=None,
    )
    assert pack.plan.skipped is False
    assert pack.plan.overlays
    assert pack.plan.motion_plan
    kinds = {o.kind for o in pack.plan.overlays}
    assert kinds <= _VALID
    assert "animated_title" in kinds
    assert "lower_third" in kinds
    assert "statistic" in kinds or "chart" in kinds
    assert "educational_overlay" in kinds


def test_inject_analyze_fn() -> None:
    clear_motion_graphics_cache()

    def _fake(**_: object) -> GeminiMotionGraphicsBatch:
        return GeminiMotionGraphicsBatch(
            overlays=[
                MotionOverlay(
                    scene=1,
                    kind="kinetic_typography",
                    text="NOW",
                    style="bold",
                    animation="slam",
                    timing="0-1s",
                    position="center",
                )
            ]
        )

    pack = build_motion_graphics_pack(enabled=True, analyze_fn=_fake)
    assert pack.plan.provider == "gemini"
    assert pack.plan.overlays[0].kind == "kinetic_typography"
    assert "scene 1:" in pack.plan.motion_plan[0]
