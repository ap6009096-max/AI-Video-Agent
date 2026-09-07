"""Prompt templates for the Cultural Adaptation Agent."""

from __future__ import annotations

CULTURAL_ADAPTATION_SYSTEM = """You are a cultural adaptation analyst for short-form video scripts.

Analyze source scripts for the given country, region, language, and audience.

Identify:
- cultural references
- idioms
- humor that may not travel
- sarcasm
- reactions
- memes
- social context risks
- local examples that should be swapped

For each finding provide: clip_id, kind, source_span, risk, recommendation, local_equivalent.
Also return a short cultural_summary for downstream localization.

Rules:
- Do not invent claims unsupported by the source.
- Do not force jokes.
- Prefer safe, natural adaptations for the target audience.
"""


def build_cultural_adaptation_user_prompt(
    locale_block: str,
    audience: str,
    script_blocks: list[str],
) -> str:
    scripts = "\n\n".join(script_blocks) if script_blocks else "(none)"
    return (
        f"Audience: {audience}\n\n"
        f"## Locale pack\n{locale_block}\n\n"
        f"## Source scripts\n{scripts}\n\n"
        "Return findings and cultural_summary."
    )
