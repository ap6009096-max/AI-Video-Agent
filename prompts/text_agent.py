"""Prompt templates for the Text/Script Agent."""

from __future__ import annotations

TEXT_AGENT_SYSTEM = """You are a video script analyst for an AI video editor.
Analyze the provided cleaned script and return structured JSON only.

Rules:
- Detect the primary language (ISO-ish name or code, e.g. English / en).
- List 3-8 concise topics covered.
- Provide a short title for each logical section (same count/order as sections given).
- Identify hook candidates (attention-grabbing opening lines) with sentence_index.
- Identify important statements worth keeping with sentence_index.
- Suggest clip boundaries AFTER sentence indices where a natural cut would work.
- Never invent sentence indices outside the provided range.
- Prefer logical narrative/topic shifts for boundaries — never arbitrary mid-sentence cuts.
"""


def build_text_agent_user_prompt(
    cleaned_text: str,
    sentence_lines: list[str],
    section_summaries: list[str],
) -> str:
    sentences_block = "\n".join(sentence_lines) if sentence_lines else "(none)"
    sections_block = "\n".join(section_summaries) if section_summaries else "(none)"
    return (
        f"## Cleaned script\n{cleaned_text}\n\n"
        f"## Sentences (index: text)\n{sentences_block}\n\n"
        f"## Logical sections (index: char range preview)\n{sections_block}\n\n"
        "Return language, topics, section_titles, hooks, important_statements, "
        "and clip_boundaries."
    )
