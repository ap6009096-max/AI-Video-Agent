"""Prompt templates for the Director Agent (continuity & sequencing)."""

from __future__ import annotations

DIRECTOR_AGENT_SYSTEM = """You are a film/video director for short-form and long-form content.

Given script, optional storyboard, stories, visual style, and environment, produce a
director plan that makes scenes connect naturally.

Return:
- scene_order: list of 1-based scene ints in the preferred playback order
- continuity_notes: short strings covering story, character, environment, camera,
  and transition continuity between adjacent scenes
- camera_flow: short strings describing how the camera should progress shot-to-shot

Rules:
- Prefer storyboard scene numbers when provided; reorder only when continuity improves.
- Ensure character, environment, story, and camera continuity across cuts.
- Keep lists concise (max ~12 scenes / notes / flow lines).
- Do not call or name video vendor APIs.
"""


def build_director_agent_user_prompt(
    *,
    style: str,
    environment: str,
    audience: str,
    title: str,
    hook: str,
    script_block: str,
    storyboard_block: str,
    story_block: str,
    camera_vocab: str,
) -> str:
    return (
        f"Visual style: {style or '(none)'}\n"
        f"Environment: {environment or '(none)'}\n"
        f"Audience: {audience or 'General'}\n\n"
        f"Title: {title or '(none)'}\n"
        f"Hook: {hook or '(none)'}\n\n"
        f"## Camera flow vocabulary\n{camera_vocab or '(none)'}\n\n"
        f"## Script\n{script_block or '(none)'}\n\n"
        f"## Storyboard (if any)\n{storyboard_block or '(none)'}\n\n"
        f"## Stories (if any)\n{story_block or '(none)'}\n\n"
        "Return scene_order, continuity_notes, and camera_flow so scenes connect "
        "naturally with story, character, environment, and camera continuity."
    )
