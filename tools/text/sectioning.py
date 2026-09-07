"""Logical sectioning for long scripts (never mid-sentence arbitrary cuts)."""

from __future__ import annotations

from schemas.transcript import ScriptParagraph, ScriptSection, ScriptSentence

TARGET_MIN = 800
TARGET_MAX = 1500


def build_logical_sections(
    text: str,
    paragraphs: list[ScriptParagraph],
    sentences: list[ScriptSentence],
    *,
    target_min: int = TARGET_MIN,
    target_max: int = TARGET_MAX,
) -> list[ScriptSection]:
    """Group paragraphs into logical sections sized by content, not fixed slices."""
    if not text.strip():
        return []

    if not paragraphs:
        return [
            ScriptSection(
                id="sec0",
                title="Section 1",
                start_char=0,
                end_char=len(text),
                sentence_ids=[s.id for s in sentences],
            )
        ]

    # Short text: one section per paragraph (or single section if tiny)
    total_len = len(text)
    if total_len <= target_max:
        if len(paragraphs) == 1:
            p = paragraphs[0]
            return [
                ScriptSection(
                    id="sec0",
                    title="Section 1",
                    start_char=p.start_char,
                    end_char=p.end_char,
                    sentence_ids=list(p.sentence_ids),
                )
            ]
        # Keep paragraph boundaries as sections when few
        if len(paragraphs) <= 6:
            return [
                ScriptSection(
                    id=f"sec{i}",
                    title=f"Section {i + 1}",
                    start_char=p.start_char,
                    end_char=p.end_char,
                    sentence_ids=list(p.sentence_ids),
                )
                for i, p in enumerate(paragraphs)
            ]

    # Merge paragraphs into topic-sized buckets
    sections: list[ScriptSection] = []
    bucket: list[ScriptParagraph] = []
    bucket_len = 0

    def _flush() -> None:
        nonlocal bucket, bucket_len
        if not bucket:
            return
        idx = len(sections)
        start = bucket[0].start_char
        end = bucket[-1].end_char
        sids: list[str] = []
        for p in bucket:
            sids.extend(p.sentence_ids)
        sections.append(
            ScriptSection(
                id=f"sec{idx}",
                title=f"Section {idx + 1}",
                start_char=start,
                end_char=end,
                sentence_ids=sids,
            )
        )
        bucket = []
        bucket_len = 0

    for p in paragraphs:
        p_len = max(1, p.end_char - p.start_char)
        if bucket and bucket_len + p_len > target_max and bucket_len >= target_min:
            _flush()
        bucket.append(p)
        bucket_len += p_len
        if bucket_len >= target_max:
            _flush()

    _flush()
    return sections
