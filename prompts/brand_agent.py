"""Prompt templates for the Brand Agent."""

from __future__ import annotations

BRAND_AGENT_SYSTEM = """You are a brand kit editor.

Given an existing brand name, audience, and seed tone/tagline/pillars, refine
brand voice and CTA messaging only. Do not invent logos, trademarks, or legal
claims. Keep outputs concise and production-ready.
"""


def build_brand_agent_user_prompt(
    *,
    brand_name: str,
    audience: str,
    platform: str,
    tone: str,
    tagline: str,
    pillars: list[str],
) -> str:
    pillar_block = "; ".join(pillars[:8]) if pillars else "(none)"
    return (
        f"Brand name: {brand_name}\n"
        f"Audience: {audience}\n"
        f"Platform: {platform}\n"
        f"Seed tone: {tone}\n"
        f"Seed tagline: {tagline}\n"
        f"Seed pillars: {pillar_block}\n"
        "Refine tone, personality, tagline, preferred CTA phrases, and pillars."
    )
