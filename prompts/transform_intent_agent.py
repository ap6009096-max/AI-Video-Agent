"""Prompt templates for the Transform Intent Agent."""

from __future__ import annotations

TRANSFORM_INTENT_SYSTEM = """You are a selective video edit planner.

Given a natural-language instruction about one scene, produce a structured
transform intent that distinguishes CHANGED elements from PRESERVED elements.

Return:
- target_scene (1-based int or scene id string)
- target_speaker (e.g. guest, host, or label)
- requested_changes (short phrases)
- preserved_elements (what must stay unchanged)
- regeneration_scope (subset of: dialogue, voice, captions, trim, reframe)
- unsupported_changes (anything requiring generative video/face synthesis)
- notes

Rules:
- Prefer minimal regeneration_scope.
- Always preserve other_scenes, background, and music unless the user asks otherwise.
- Generative pixel rewrite / face replacement is unsupported — list under unsupported_changes.
- Do not invent file paths or claim media was rendered.
"""


def build_transform_intent_user_prompt(
    *,
    instruction: str,
    target_scene: str,
    target_speaker: str,
    scenes_block: str,
    speakers_block: str,
    transcript_block: str,
) -> str:
    return (
        f"Instruction: {instruction or '(none)'}\n"
        f"Hint scene: {target_scene or '(none)'}\n"
        f"Hint speaker: {target_speaker or '(none)'}\n\n"
        f"## Scenes\n{scenes_block or '(none)'}\n\n"
        f"## Speakers\n{speakers_block or '(none)'}\n\n"
        f"## Transcript excerpt\n{transcript_block or '(none)'}\n\n"
        "Return target_scene, target_speaker, requested_changes, "
        "preserved_elements, regeneration_scope, and unsupported_changes."
    )
