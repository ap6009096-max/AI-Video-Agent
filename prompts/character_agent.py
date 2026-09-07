"""Prompt templates for the Character Management Agent."""

from __future__ import annotations

CHARACTER_AGENT_SYSTEM = """You are a character / cast bible designer for video production.

Given script, optional storyboard, stories, visual style, and environment, produce a
durable character list so appearance, clothing, voice, personality, and expressions
stay consistent across scenes.

Supported role_type values (exactly):
- human
- narrator
- ai_avatar
- mascot
- animated

For each character return:
- name, role_type, appearance, clothing, voice, personality, expressions (list),
  scene_ids (optional ints)

Also return consistency_notes: short rules for keeping each character identical
across scenes.

Rules:
- Prefer few clear cast members (max ~6).
- Narrators may be voice-only.
- Do not invent branded IP mascots.
- Do not call media APIs.
"""


def build_character_agent_user_prompt(
    *,
    style: str,
    environment: str,
    audience: str,
    title: str,
    hook: str,
    script_block: str,
    storyboard_block: str,
    story_block: str,
    voice_hint: str,
    avatar_hint: str,
    role_defaults: str,
) -> str:
    return (
        f"Visual style: {style or '(none)'}\n"
        f"Environment: {environment or '(none)'}\n"
        f"Audience: {audience or 'General'}\n"
        f"Voice config hint: {voice_hint or '(none)'}\n"
        f"Avatar config hint: {avatar_hint or '(none)'}\n\n"
        f"Title: {title or '(none)'}\n"
        f"Hook: {hook or '(none)'}\n\n"
        f"## Role-type defaults\n{role_defaults or '(none)'}\n\n"
        f"## Script\n{script_block or '(none)'}\n\n"
        f"## Storyboard (if any)\n{storyboard_block or '(none)'}\n\n"
        f"## Stories (if any)\n{story_block or '(none)'}\n\n"
        "Return characters and consistency_notes so the cast stays consistent "
        "across scenes."
    )
