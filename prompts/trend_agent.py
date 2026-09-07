"""Prompt templates for the Trend Detection Agent."""

from __future__ import annotations

TREND_AGENT_SYSTEM = """You are a short-form video trend analyst.

Given platform, audience, and content signals (title, description, tags, hashtags,
keywords, viral hooks), analyze:

- Topic classification (topic_labels)
- Trend matching (trend_topics, trending_hashtags, trending_keywords)
- Viral patterns that fit the content
- Audience relevance (short prose)
- Overall trend_score from 0 to 100
- recommended_tags (plain tags without #)

Rules:
- Do not invent live social API data; infer from provided signals + general platform norms.
- Prefer concrete, actionable tags and topics.
- Keep lists concise (max ~8 items each).
- trend_score must be between 0 and 100.
"""


def build_trend_agent_user_prompt(
    *,
    platform: str,
    audience: str,
    title: str,
    description: str,
    tags: list[str],
    hashtags: list[str],
    keywords: list[str],
    viral_hooks: list[str],
    seed_block: str,
) -> str:
    return (
        f"Platform: {platform}\n"
        f"Audience: {audience}\n\n"
        f"Title: {title or '(none)'}\n"
        f"Description: {description or '(none)'}\n"
        f"Tags: {', '.join(tags) if tags else '(none)'}\n"
        f"Hashtags: {', '.join(hashtags) if hashtags else '(none)'}\n"
        f"Keywords: {', '.join(keywords) if keywords else '(none)'}\n"
        f"Viral hooks: {'; '.join(viral_hooks) if viral_hooks else '(none)'}\n\n"
        f"## Seed catalog for platform\n{seed_block or '(none)'}\n\n"
        "Return trend_score, trend_topics, recommended_tags, trending_hashtags, "
        "trending_keywords, viral_patterns, audience_relevance, topic_labels."
    )
