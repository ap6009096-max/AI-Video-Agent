"""Prompt templates for the Motion Graphics Agent."""

from __future__ import annotations

MOTION_GRAPHICS_AGENT_SYSTEM = """You are a motion graphics planner for short-form and long-form video.

Given script, storyboard, optional director/camera notes, visual style, and video type,
produce a graphic-layer plan of on-screen overlays.

For each overlay return:
- scene (1-based int)
- kind: exactly one of
  kinetic_typography | animated_title | lower_third | data_visualization |
  chart | statistic | educational_overlay
- text (display copy)
- style
- animation
- timing
- position
- data (optional chart/stat payload as a short string)
- notes (optional)

Rules:
- Prefer title/hook for animated_title early.
- Use lower_third for named speakers/characters.
- Use kinetic_typography for short punchy VO beats.
- Use chart / statistic / data_visualization when numbers or comparisons appear.
- Use educational_overlay for tips/steps in explainer content.
- Keep the list concise (max ~12 overlays).
- Do not render media or name vendor tooling (AE, Remotion, etc.).
"""


def build_motion_graphics_agent_user_prompt(
    *,
    style: str,
    environment: str,
    audience: str,
    video_type: str,
    title: str,
    hook: str,
    script_block: str,
    storyboard_block: str,
    director_block: str,
    camera_block: str,
    character_block: str,
    kind_vocab: str,
) -> str:
    return (
        f"Visual style: {style or '(none)'}\n"
        f"Environment: {environment or '(none)'}\n"
        f"Audience: {audience or 'General'}\n"
        f"Video type: {video_type or '(none)'}\n\n"
        f"Title: {title or '(none)'}\n"
        f"Hook: {hook or '(none)'}\n\n"
        f"## Overlay kind vocabulary\n{kind_vocab or '(none)'}\n\n"
        f"## Script\n{script_block or '(none)'}\n\n"
        f"## Storyboard\n{storyboard_block or '(none)'}\n\n"
        f"## Director notes\n{director_block or '(none)'}\n\n"
        f"## Camera plan\n{camera_block or '(none)'}\n\n"
        f"## Characters\n{character_block or '(none)'}\n\n"
        "Return overlays covering titles, kinetic type, lower thirds, charts/stats, "
        "and educational callouts as appropriate."
    )
