"""Prompt templates for the Camera Planning Agent."""

from __future__ import annotations

CAMERA_AGENT_SYSTEM = """You are a camera / cinematography planner for short-form and long-form video.

Given script, storyboard, optional cast bible, visual style, and environment, produce
per-scene camera instructions.

For each scene return:
- scene (1-based int)
- shot_type: exactly one of
  wide | medium | close_up | extreme_close_up | drone | tracking | pov | cinematic
- movement (short phrase)
- instruction (full operator-ready sentence)
- lens (optional)
- notes (optional)

Rules:
- Cover every storyboard scene when provided.
- Prefer storyboard camera hints when present; normalize to the shot_type enum.
- Vary framing across the sequence when it serves continuity.
- Do not call media APIs or name video vendors.
"""


def build_camera_agent_user_prompt(
    *,
    style: str,
    environment: str,
    audience: str,
    title: str,
    hook: str,
    script_block: str,
    storyboard_block: str,
    character_block: str,
    shot_vocab: str,
) -> str:
    return (
        f"Visual style: {style or '(none)'}\n"
        f"Environment: {environment or '(none)'}\n"
        f"Audience: {audience or 'General'}\n\n"
        f"Title: {title or '(none)'}\n"
        f"Hook: {hook or '(none)'}\n\n"
        f"## Shot type vocabulary\n{shot_vocab or '(none)'}\n\n"
        f"## Script\n{script_block or '(none)'}\n\n"
        f"## Storyboard (if any)\n{storyboard_block or '(none)'}\n\n"
        f"## Characters (if any)\n{character_block or '(none)'}\n\n"
        "Return instructions for every scene with scene, shot_type, movement, "
        "and instruction."
    )
