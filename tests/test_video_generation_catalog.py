"""Tests for video generation catalog."""

from __future__ import annotations

from schemas.job import VideoJobConfig
from schemas.video_generation import GeminiVideoGenerationBatch, VideoGenShot
from tools.video_generation.catalog import (
    build_video_generation_pack,
    clear_video_generation_cache,
    resolve_mode,
)


def test_flag_off_skips() -> None:
    clear_video_generation_cache()
    pack = build_video_generation_pack(enabled=False)
    assert pack.plan.skipped is True
    assert pack.plan.shots == []
    assert pack.plan.provider == "none"


def test_resolve_mode_aliases() -> None:
    clear_video_generation_cache()
    assert resolve_mode("Explainer") == "Explainer"
    assert resolve_mode("Educational") == "Explainer"
    assert resolve_mode("AI Avatar") == "AI Avatar"
    assert resolve_mode("Motion Graphics") == "Motion Graphics"
    assert resolve_mode("Unknown Type") == "Cinematic"


def test_heuristic_pack_has_plans() -> None:
    clear_video_generation_cache()
    pack = build_video_generation_pack(
        enabled=True,
        config=VideoJobConfig(
            video_type="Documentary",
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
    assert pack.plan.scene_prompts
    assert pack.plan.shot_sequence
    assert pack.plan.camera_movement_plan
    assert pack.plan.mode == "Documentary"
    assert pack.plan.provider in {"heuristic", "gemini"}
    assert pack.plan.provider not in {"runway", "pika", "luma", "veo"}
    for shot in pack.plan.shots:
        assert shot.scene >= 1
        assert shot.duration > 0
        assert shot.prompt
        assert shot.camera_move


def test_prefers_storyboard_rows() -> None:
    clear_video_generation_cache()
    pack = build_video_generation_pack(
        enabled=True,
        config=VideoJobConfig(video_type="Cinematic"),
        storyboard_pack={
            "plan": {
                "skipped": False,
                "shots": [
                    {
                        "scene": 1,
                        "duration": 4,
                        "camera": "wide establishing",
                        "visual": "Misty trail",
                        "voiceover": "Open",
                        "transition": "cut",
                    }
                ],
            }
        },
        analyze_fn=None,
    )
    assert len(pack.plan.shots) == 1
    assert "Misty trail" in pack.plan.shots[0].prompt
    assert pack.plan.shots[0].camera_move == "wide establishing"


def test_director_reorders_storyboard_rows() -> None:
    clear_video_generation_cache()
    pack = build_video_generation_pack(
        enabled=True,
        config=VideoJobConfig(video_type="Cinematic"),
        storyboard_pack={
            "plan": {
                "skipped": False,
                "shots": [
                    {
                        "scene": 1,
                        "duration": 4,
                        "camera": "wide",
                        "visual": "First",
                        "voiceover": "A",
                        "transition": "cut",
                    },
                    {
                        "scene": 2,
                        "duration": 5,
                        "camera": "close-up",
                        "visual": "Second",
                        "voiceover": "B",
                        "transition": "fade",
                    },
                ],
            }
        },
        director_pack={
            "plan": {
                "skipped": False,
                "scene_order": [2, 1],
            }
        },
        analyze_fn=None,
    )
    assert "Second" in pack.plan.shots[0].prompt
    assert "First" in pack.plan.shots[1].prompt
    assert pack.plan.shots[0].camera_move == "close-up"

def test_inject_analyze_fn() -> None:
    clear_video_generation_cache()

    def _fake(**_: object) -> GeminiVideoGenerationBatch:
        return GeminiVideoGenerationBatch(
            shots=[
                VideoGenShot(
                    scene=1,
                    duration=4,
                    prompt="Slow push into forest path",
                    visual_style="Cinematic",
                    environment="Forest",
                    camera_move="slow push-in",
                    shot_type="establishing",
                    transition="cut",
                    voiceover="Walk in",
                ),
                VideoGenShot(
                    scene=2,
                    duration=5,
                    prompt="Close leaves detail",
                    visual_style="Cinematic",
                    environment="Forest",
                    camera_move="orbit",
                    shot_type="close-up",
                    transition="dissolve",
                    voiceover="Notice details",
                ),
            ]
        )

    pack = build_video_generation_pack(enabled=True, analyze_fn=_fake)
    assert pack.plan.provider == "gemini"
    assert len(pack.plan.shots) == 2
    assert pack.plan.scene_prompts[0].startswith("Slow push")
    assert "scene 1:" in pack.plan.camera_movement_plan[0]
    assert pack.plan.provider not in {"runway", "pika", "luma"}
