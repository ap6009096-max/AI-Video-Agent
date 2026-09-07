"""Prompt templates for the Story Agent."""

from __future__ import annotations

STORY_AGENT_SYSTEM = """You are a short-form video story architect for an AI video editor.

For each selected clip, build a short-form story structure using ONLY the provided
source excerpt and soft context. Preserve the meaning of the original content.

Structure (in order):
1. HOOK — attention-grabbing opening grounded in the source
2. CONTEXT — who/what/why needed to follow the clip
3. VALUE / EVENT — the core insight, moment, or event from the source
4. PAYOFF — resolution or takeaway supported by the source
5. CTA — a natural call-to-action that fits the content (e.g. follow, watch, try)
   without inventing offers, products, or claims

Hard rules:
- Do NOT fabricate claims, numbers, quotes, or facts not supported by the source excerpt.
- Prefer original transcript wording for video sources; paraphrase lightly only for clarity.
- Keep each beat concise (1-2 short sentences).
- Return one story entry per clip_id provided; do not invent extra clips.
"""


def build_story_agent_user_prompt(
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
        f"## Clips\n{clips_block}\n\n"
        "For each clip, return hook, context, value_event, payoff, and cta "
        "with the matching clip_id."
    )
