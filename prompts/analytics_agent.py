"""Prompt templates for the Analytics Prediction Agent."""

from __future__ import annotations

ANALYTICS_AGENT_SYSTEM = """You are a short-form video performance prediction analyst.

Given platform, audience, and content signals (title, hook, SEO, trend score,
viral scores, thumbnail plan), estimate predicted performance scores from 0 to 100:

- engagement_score — likes/comments/saves potential
- retention_score — how well viewers stay through the piece
- shareability_score — likelihood of shares/reposts
- watch_time_score — predicted relative watch-time strength
- ctr_score — click-through potential from title/thumbnail

Also return short driver lists and a brief rationale.

Rules:
- This is a prediction model, not a guarantee. Never claim certainty.
- Do not invent live analytics or historical channel data.
- Infer only from provided signals and general platform norms.
- All scores must be between 0 and 100.
- Keep driver lists concise (max ~5 items each).
"""


def build_analytics_agent_user_prompt(
    *,
    platform: str,
    audience: str,
    title: str,
    hook: str,
    description: str,
    tags: list[str],
    hashtags: list[str],
    keywords: list[str],
    trend_score: float,
    viral_final: float,
    viral_shareability: float,
    thumbnail_text: str,
    thumbnail_emotion: str,
    thumbnail_layout: str,
    weight_block: str,
) -> str:
    return (
        f"Platform: {platform}\n"
        f"Audience: {audience}\n\n"
        f"Title: {title or '(none)'}\n"
        f"Hook: {hook or '(none)'}\n"
        f"Description: {description or '(none)'}\n"
        f"Tags: {', '.join(tags) if tags else '(none)'}\n"
        f"Hashtags: {', '.join(hashtags) if hashtags else '(none)'}\n"
        f"Keywords: {', '.join(keywords) if keywords else '(none)'}\n"
        f"Trend score: {trend_score}\n"
        f"Viral final_score: {viral_final}\n"
        f"Viral shareability: {viral_shareability}\n"
        f"Thumbnail text: {thumbnail_text or '(none)'}\n"
        f"Thumbnail emotion: {thumbnail_emotion or '(none)'}\n"
        f"Thumbnail layout: {thumbnail_layout or '(none)'}\n\n"
        f"## Heuristic weight hints\n{weight_block or '(none)'}\n\n"
        "Return engagement_score, retention_score, shareability_score, "
        "watch_time_score, ctr_score, engagement_drivers, retention_drivers, "
        "shareability_drivers, and rationale. "
        "Remember: this is a prediction model, not a guarantee."
    )
