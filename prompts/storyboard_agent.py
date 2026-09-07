"""Prompt templates for the Storyboard Agent."""

from __future__ import annotations

STORYBOARD_AGENT_SYSTEM = """You are a video storyboard director for short-form and long-form content.

Given transcript, script, and optional scene/story signals plus visual style and
environment, produce a complete shot list for visual storytelling BEFORE render.

For each shot return:
- scene (1-based integer)
- duration (seconds, typically 2–8 for Shorts)
- camera (camera move / framing)
- visual (what is on screen)
- voiceover (spoken line or empty)
- transition (into the NEXT shot; last shot may be "end" or "fade")

Also keep the list concise (max ~12 shots). Prefer concrete, filmable directions.
Do not invent stock footage URLs.
"""


def build_storyboard_agent_user_prompt(
    *,
    style: str,
    environment: str,
    audience: str,
    title: str,
    hook: str,
    script_block: str,
    transcript_excerpt: str,
    scene_block: str,
    story_block: str,
    camera_vocab: str,
    transition_vocab: str,
) -> str:
    return (
        f"Visual style: {style or '(none)'}\n"
        f"Environment: {environment or '(none)'}\n"
        f"Audience: {audience or 'General'}\n\n"
        f"Title: {title or '(none)'}\n"
        f"Hook: {hook or '(none)'}\n\n"
        f"## Script\n{script_block or '(none)'}\n\n"
        f"## Transcript excerpt\n{transcript_excerpt or '(none)'}\n\n"
        f"## Detected scenes\n{scene_block or '(none)'}\n\n"
        f"## Story beats\n{story_block or '(none)'}\n\n"
        f"## Camera vocabulary\n{camera_vocab or '(none)'}\n\n"
        f"## Transition vocabulary\n{transition_vocab or '(none)'}\n\n"
        "Return shots with scene, duration, camera, visual, voiceover, transition."
    )
