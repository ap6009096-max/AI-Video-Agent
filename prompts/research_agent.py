"""Prompt templates for the Research Agent (optional Gemini enrichment)."""

from __future__ import annotations

RESEARCH_AGENT_SYSTEM = """You enrich a research report for an AI video editor.

You receive an already-built corpus of SOURCES and CLAIMS. You may improve:
- topic analysis (primary topic, subtopics, audience, angle, keywords)
- outline section titles/summaries/bullets
- a short research summary paragraph

Hard rules:
- Do NOT invent new factual claims or sources.
- Outline claim_ids MUST be a subset of the provided claim ids.
- Do NOT invent URLs, statistics, or quotes.
- Prefer concise, video-ready language.
"""


def build_research_enrich_user_prompt(
    *,
    topic: str,
    sources_block: str,
    claims_block: str,
    outline_block: str,
    summary: str,
) -> str:
    return (
        f"Topic seed: {topic or '(unknown)'}\n\n"
        f"Sources (read-only):\n{sources_block or '(none)'}\n\n"
        f"Claims (read-only; use these ids only):\n{claims_block or '(none)'}\n\n"
        f"Current outline:\n{outline_block or '(none)'}\n\n"
        f"Current summary:\n{summary or '(none)'}\n\n"
        "Return improved topic analysis, outline (claim_ids from the list only), "
        "and summary."
    )
