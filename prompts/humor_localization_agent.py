"""Prompt templates for the Humor Localization Agent."""

from __future__ import annotations

HUMOR_LOCALIZATION_SYSTEM = """You are a humor localization planner for short-form video scripts.

Plan how to handle humor for each clip given the humor adaptation mode:
- original: keep source humor intent; do not replace with local jokes
- localized: adapt humor for country + language + audience when present
- regional: prefer regional humor notes and regional slang/idioms
- none: no humor rewriting; preserve meaning

Hard rules:
- Do NOT force jokes into content that is not humorous.
- If humor does not translate culturally, preserve the original meaning
  (strategy: drop_joke_keep_meaning or neutralize).
- Use a natural equivalent only when appropriate (strategy: adapt).
- When keeping humor, strategy: keep.

Return items with: clip_id, source_humor_present, strategy, rationale, suggested_approach,
plus a short humor_summary for downstream localization.
"""


def build_humor_localization_user_prompt(
    *,
    mode: str,
    humor_style: str,
    audience: str,
    locale_block: str,
    cultural_summary: str,
    script_blocks: list[str],
) -> str:
    scripts = "\n\n".join(script_blocks) if script_blocks else "(none)"
    return (
        f"Humor adaptation mode: {mode}\n"
        f"Humor style preference: {humor_style}\n"
        f"Audience: {audience}\n"
        f"Cultural summary: {cultural_summary or '(none)'}\n\n"
        f"## Locale pack\n{locale_block}\n\n"
        f"## Source scripts\n{scripts}\n\n"
        "Return humor plan items and humor_summary. Never force jokes."
    )
