"""Tests for character catalog."""

from __future__ import annotations

from schemas.character import CharacterProfile, GeminiCharacterBatch
from schemas.job import VideoJobConfig
from tools.character.catalog import build_character_pack, clear_character_cache


def test_flag_off_skips() -> None:
    clear_character_cache()
    pack = build_character_pack(enabled=False)
    assert pack.plan.skipped is True
    assert pack.plan.characters == []
    assert pack.plan.provider == "none"


def test_heuristic_pack_has_profiles() -> None:
    clear_character_cache()
    pack = build_character_pack(
        enabled=True,
        config=VideoJobConfig(
            visual_style="Cinematic",
            environment="Wildlife/Nature Forest",
            voice="Warm Narrator",
        ),
        script_pack={
            "primary": {
                "title": "Forest tips",
                "hook": "Walk into the mist.",
                "script": "Explore quiet trails at dawn. Listen for birds.",
            }
        },
        storyboard_pack={
            "plan": {
                "skipped": False,
                "shots": [
                    {
                        "scene": 1,
                        "camera": "wide",
                        "visual": "Host on trail",
                        "voiceover": "Walk into the mist",
                        "transition": "cut",
                    }
                ],
            }
        },
        analyze_fn=None,
    )
    assert pack.plan.skipped is False
    assert len(pack.plan.characters) >= 1
    assert pack.plan.consistency_notes
    for c in pack.plan.characters:
        assert c.name
        assert c.role_type in {
            "human",
            "narrator",
            "ai_avatar",
            "mascot",
            "animated",
        }
        assert c.appearance
        assert c.clothing
        assert c.voice
        assert c.personality
        assert isinstance(c.expressions, list)


def test_inject_analyze_fn() -> None:
    clear_character_cache()

    def _fake(**_: object) -> GeminiCharacterBatch:
        return GeminiCharacterBatch(
            characters=[
                CharacterProfile(
                    name="Ava",
                    role_type="ai_avatar",
                    appearance="digital presenter",
                    clothing="studio blazer",
                    voice="clear mid register",
                    personality="helpful",
                    expressions=["smile", "nod"],
                    scene_ids=[1, 2],
                )
            ],
            consistency_notes=["Keep Ava wardrobe identical across scenes."],
        )

    pack = build_character_pack(enabled=True, analyze_fn=_fake)
    assert pack.plan.provider == "gemini"
    assert len(pack.plan.characters) == 1
    assert pack.plan.characters[0].name == "Ava"
    assert pack.plan.characters[0].role_type == "ai_avatar"
    assert pack.plan.consistency_notes
