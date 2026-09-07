"""Tests for storyboard catalog."""

from __future__ import annotations

from schemas.job import VideoJobConfig
from schemas.storyboard import GeminiStoryboardBatch, StoryboardShot
from tools.storyboard.catalog import build_storyboard_pack, clear_storyboard_cache


def test_flag_off_skips() -> None:
    clear_storyboard_cache()
    pack = build_storyboard_pack(enabled=False)
    assert pack.plan.skipped is True
    assert pack.plan.shots == []
    assert pack.plan.provider == "none"


def test_heuristic_pack() -> None:
    clear_storyboard_cache()
    pack = build_storyboard_pack(
        enabled=True,
        config=VideoJobConfig(
            visual_style="Cinematic",
            environment="Wildlife/Nature Forest",
        ),
        script_pack={
            "primary": {
                "title": "Forest tips",
                "hook": "Walk into the mist.",
                "script": "Explore quiet trails at dawn. Listen for birds. End with a clear CTA.",
            }
        },
        analyze_fn=None,
    )
    assert pack.plan.skipped is False
    assert len(pack.plan.shots) >= 2
    assert pack.plan.shot_list
    assert pack.plan.scene_list
    assert pack.plan.camera_plan
    assert pack.plan.transition_plan
    for shot in pack.plan.shots:
        assert shot.scene >= 1
        assert shot.duration > 0
        assert shot.camera
        assert shot.visual
        assert shot.transition


def test_inject_analyze_fn() -> None:
    clear_storyboard_cache()

    def _fake(**_: object) -> GeminiStoryboardBatch:
        return GeminiStoryboardBatch(
            shots=[
                StoryboardShot(
                    scene=1,
                    duration=4,
                    camera="wide establishing",
                    visual="Misty trail open",
                    voiceover="Walk into the mist",
                    transition="cut",
                ),
                StoryboardShot(
                    scene=2,
                    duration=5,
                    camera="close-up",
                    visual="Leaves in detail",
                    voiceover="Notice the details",
                    transition="fade",
                ),
            ]
        )

    pack = build_storyboard_pack(enabled=True, analyze_fn=_fake)
    assert pack.plan.provider == "gemini"
    assert len(pack.plan.shots) == 2
    assert pack.plan.shots[0].camera == "wide establishing"
    assert "scene 1:" in pack.plan.camera_plan[0]
