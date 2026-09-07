"""Prompt templates for the Content Repurposing Agent."""

from __future__ import annotations

REPURPOSE_AGENT_SYSTEM = """You are a content repurposing specialist.

Convert one source into multiple distribution formats. Ground every claim in the
provided source excerpt. Do not invent facts, quotes, or timings.

Produce:
- reels: short spoken/on-screen script for Instagram Reels
- shorts: short spoken script for YouTube Shorts
- tiktok: native TikTok-style script
- blog_summary: concise blog-style summary
- linkedin_post: professional LinkedIn post
- twitter_thread: list of short tweets forming a thread
- instagram_caption: caption with light hashtags when appropriate
- newsletter_summary: email-friendly summary

Match tone to the source_kind (video, podcast, article, transcript) and keep
outputs concise and ready to paste.
"""


def build_repurpose_agent_user_prompt(
    *,
    source_kind: str,
    platform: str,
    audience: str,
    source_excerpt: str,
    title: str,
    hook: str,
    hashtags: list[str],
    trend_topics: list[str],
    format_hints: str,
) -> str:
    tags = ", ".join(hashtags) if hashtags else "(none)"
    topics = ", ".join(trend_topics) if trend_topics else "(none)"
    return (
        f"Source kind: {source_kind}\n"
        f"Platform context: {platform}\n"
        f"Audience: {audience}\n"
        f"Title: {title or '(none)'}\n"
        f"Hook: {hook or '(none)'}\n"
        f"Hashtags: {tags}\n"
        f"Trend topics: {topics}\n\n"
        f"## Format hints\n{format_hints or '(none)'}\n\n"
        f"## Source excerpt\n{source_excerpt or '(none)'}\n\n"
        "Return all format fields."
    )
