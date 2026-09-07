"""Prompt templates for the Image Generation Agent."""

from __future__ import annotations

IMAGE_AGENT_SYSTEM = """You are a visual prompt designer for short-form video production.

Given script/transcript/scene signals plus visual style and environment, produce
image generation prompts for these kinds as needed:
- scene — key scene stills
- storyboard — storyboard frames
- broll — B-roll / cutaway visuals
- thumbnail — clickable thumbnail composition
- background — background / environment plates

For each item return: scene_id, prompt, style, environment, kind.

Rules:
- Prompts must be concrete, visual, and suitable for an image model.
- Respect the provided style and environment.
- Keep the list concise (max ~8 items).
- Do not invent live stock URLs; prompts only.
- scene_id should be stable short ids like scene_1, storyboard_1, thumb_1.
"""


def build_image_agent_user_prompt(
    *,
    style: str,
    environment: str,
    audience: str,
    title: str,
    hook: str,
    scene_block: str,
    script_block: str,
    transcript_excerpt: str,
    kind_hints: str,
) -> str:
    return (
        f"Visual style: {style or '(none)'}\n"
        f"Environment: {environment or '(none)'}\n"
        f"Audience: {audience or 'General'}\n\n"
        f"Title: {title or '(none)'}\n"
        f"Hook: {hook or '(none)'}\n\n"
        f"## Scenes / storyboard signals\n{scene_block or '(none)'}\n\n"
        f"## Script signals\n{script_block or '(none)'}\n\n"
        f"## Transcript excerpt\n{transcript_excerpt or '(none)'}\n\n"
        f"## Kind hints\n{kind_hints or '(none)'}\n\n"
        "Return items with scene_id, prompt, style, environment, kind."
    )
