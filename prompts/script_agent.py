"""Prompt templates for the Script Agent (post-story copy)."""

from __future__ import annotations

SCRIPT_AGENT_SYSTEM = """You are a short-form video script writer for an AI video editor.

For each clip, turn the provided story structure and source excerpt into publishable
copy fields. Preserve the meaning of the original content.

Generate for each clip:
- title — short, punchy clip title
- hook — opening line that matches the story HOOK
- short_script — spoken/on-screen script covering HOOK→CONTEXT→VALUE/EVENT→PAYOFF→CTA
- caption — social caption (1-3 short sentences)
- cta — call to action
- thumbnail_text — 2-5 words suitable for a thumbnail
- keywords — 3-8 searchable keywords

Hard rules:
- Derive ALL fields ONLY from the story structure + source excerpt.
- Do NOT fabricate claims, statistics, quotes, or offers absent from the source.
- Prefer original transcript phrasing when it fits short-form delivery.
- Keep tone suitable for short-form social video.
- Return one script entry per clip_id; do not invent extra clips.
"""


def build_script_agent_user_prompt(
    clip_blocks: list[str],
    *,
    video_type: str = "Shorts",
    country: str = "",
    video_type_block: str = "",
    visual_style_block: str = "",
    environment_block: str = "",
    research_block: str = "",
) -> str:
    clips_block = "\n\n".join(clip_blocks) if clip_blocks else "(none)"
    locale = f"\nAudience locale hint: {country}" if country.strip() else ""
    type_header = (
        video_type_block.strip()
        if video_type_block.strip()
        else f"Video type: {video_type}"
    )
    style_header = (
        f"\n\n{visual_style_block.strip()}" if visual_style_block.strip() else ""
    )
    env_header = (
        f"\n\n{environment_block.strip()}" if environment_block.strip() else ""
    )
    research_header = (
        f"\n\n{research_block.strip()}" if research_block.strip() else ""
    )
    return (
        f"{type_header}{style_header}{env_header}{research_header}{locale}\n\n"
        f"## Clips with story structure\n{clips_block}\n\n"
        "For each clip, return title, hook, short_script, caption, cta, "
        "thumbnail_text, and keywords with the matching clip_id."
    )
