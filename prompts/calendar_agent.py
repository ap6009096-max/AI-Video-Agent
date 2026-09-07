"""Prompt templates for the Content Calendar Agent."""

from __future__ import annotations

CALENDAR_AGENT_SYSTEM = """You are a content calendar planner.

Given seed topics and a list of publish dates, produce short, concrete topic
titles suitable for a social video calendar. Do not invent sources or URLs.
Keep each topic under 90 characters. Return one topic per date when possible.
"""


def build_calendar_agent_user_prompt(
    *,
    platform: str,
    video_type: str,
    audience: str,
    seed_topics: list[str],
    dates: list[str],
) -> str:
    seeds = "; ".join(seed_topics[:24]) if seed_topics else "(none)"
    date_block = ", ".join(dates[:60]) if dates else "(none)"
    return (
        f"Platform: {platform}\n"
        f"Video type: {video_type}\n"
        f"Audience: {audience}\n"
        f"Seed topics: {seeds}\n"
        f"Dates (YYYY-MM-DD): {date_block}\n"
        "Return topics aligned to these dates."
    )
