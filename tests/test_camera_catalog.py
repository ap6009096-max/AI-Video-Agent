"""Tests for camera catalog."""

from __future__ import annotations

from schemas.camera import CameraInstruction, GeminiCameraBatch
from schemas.job import VideoJobConfig
from tools.camera.catalog import (
    build_camera_pack,
    clear_camera_cache,
    resolve_shot_type,
)


def test_flag_off_skips() -> None:
    clear_camera_cache()
    pack = build_camera_pack(enabled=False)
    assert pack.plan.skipped is True
    assert pack.plan.instructions == []
    assert pack.plan.provider == "none"


def test_resolve_shot_types() -> None:
    clear_camera_cache()
    assert resolve_shot_type("Wide shot") == "wide"
    assert resolve_shot_type("close-up") == "close_up"
    assert resolve_shot_type("extreme close-up") == "extreme_close_up"
    assert resolve_shot_type("drone") == "drone"
    assert resolve_shot_type("tracking shot") == "tracking"
    assert resolve_shot_type("POV") == "pov"
    assert resolve_shot_type("cinematic movement") == "cinematic"


def test_heuristic_pack_per_scene() -> None:
    clear_camera_cache()
    pack = build_camera_pack(
        enabled=True,
        config=VideoJobConfig(visual_style="Cinematic"),
        storyboard_pack={
            "plan": {
                "skipped": False,
                "shots": [
                    {
                        "scene": 1,
                        "camera": "wide establishing",
                        "visual": "Trail open",
                        "voiceover": "Open",
                    },
                    {
                        "scene": 2,
                        "camera": "close-up",
                        "visual": "Leaves",
                        "voiceover": "Detail",
                    },
                ],
            }
        },
        analyze_fn=None,
    )
    assert pack.plan.skipped is False
    assert len(pack.plan.instructions) == 2
    assert pack.plan.camera_plan
    for inst in pack.plan.instructions:
        assert inst.scene >= 1
        assert inst.shot_type in {
            "wide",
            "medium",
            "close_up",
            "extreme_close_up",
            "drone",
            "tracking",
            "pov",
            "cinematic",
        }
        assert inst.movement
        assert inst.instruction


def test_inject_analyze_fn() -> None:
    clear_camera_cache()

    def _fake(**_: object) -> GeminiCameraBatch:
        return GeminiCameraBatch(
            instructions=[
                CameraInstruction(
                    scene=1,
                    shot_type="drone",
                    movement="aerial glide",
                    instruction="Drone overview of the forest canopy.",
                )
            ]
        )

    pack = build_camera_pack(enabled=True, analyze_fn=_fake)
    assert pack.plan.provider == "gemini"
    assert pack.plan.instructions[0].shot_type == "drone"
    assert "scene 1:" in pack.plan.camera_plan[0]
