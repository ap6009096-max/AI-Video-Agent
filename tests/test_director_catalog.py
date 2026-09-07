"""Tests for director catalog."""

from __future__ import annotations

from schemas.director import GeminiDirectorBatch
from schemas.job import VideoJobConfig
from tools.director.catalog import build_director_pack, clear_director_cache


def test_flag_off_skips() -> None:
    clear_director_cache()
    pack = build_director_pack(enabled=False)
    assert pack.plan.skipped is True
    assert pack.plan.scene_order == []
    assert pack.plan.provider == "none"


def test_heuristic_pack_has_public_fields() -> None:
    clear_director_cache()
    pack = build_director_pack(
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
                    },
                    {
                        "scene": 2,
                        "duration": 5,
                        "camera": "close-up",
                        "visual": "Leaves",
                        "voiceover": "Detail",
                        "transition": "dissolve",
                    },
                ],
            }
        },
        analyze_fn=None,
    )
    assert pack.plan.skipped is False
    assert pack.plan.scene_order == [1, 2]
    assert pack.plan.continuity_notes
    assert pack.plan.camera_flow
    assert any("Story:" in n or "story" in n.lower() for n in pack.plan.continuity_notes)
    assert any("Character:" in n for n in pack.plan.continuity_notes)
    assert any("Environment:" in n for n in pack.plan.continuity_notes)


def test_inject_analyze_fn() -> None:
    clear_director_cache()

    def _fake(**_: object) -> GeminiDirectorBatch:
        return GeminiDirectorBatch(
            scene_order=[2, 1],
            continuity_notes=[
                "Story: Reverse open for payoff first.",
                "Camera: Match cut on eyeline.",
            ],
            camera_flow=["scene 2→1: reverse angle then establish"],
        )

    pack = build_director_pack(enabled=True, analyze_fn=_fake)
    assert pack.plan.provider == "gemini"
    assert pack.plan.scene_order == [2, 1]
    assert pack.plan.continuity_notes
    assert pack.plan.camera_flow
