"""Deterministic sentence and paragraph segmentation with char offsets."""

from __future__ import annotations

import re

from schemas.transcript import ScriptParagraph, ScriptSentence

# Split after . ! ? when followed by whitespace + capital / quote / end
_SENTENCE_RE = re.compile(
    r"(?<=[.!?])\s+(?=[\"'(A-Z0-9])|(?<=[.!?])$"
)


def split_sentences(text: str) -> list[ScriptSentence]:
    """Split cleaned text into sentences with character offsets."""
    if not text.strip():
        return []

    sentences: list[ScriptSentence] = []
    # Find candidate boundaries by scanning for .!? followed by space+capital
    parts: list[tuple[int, int, str]] = []
    start = 0
    i = 0
    while i < len(text):
        ch = text[i]
        if ch in ".!?" and i + 1 < len(text):
            # Look ahead for whitespace then content
            j = i + 1
            while j < len(text) and text[j] in "\"')":
                j += 1
            if j < len(text) and text[j].isspace():
                k = j
                while k < len(text) and text[k].isspace():
                    k += 1
                if k >= len(text) or text[k].isupper() or text[k] in "\"'(":
                    end = j
                    segment = text[start:end].strip()
                    if segment:
                        # find exact offsets of strip within [start, end)
                        abs_start = text.find(segment, start, end)
                        if abs_start < 0:
                            abs_start = start
                        parts.append((abs_start, abs_start + len(segment), segment))
                    start = k
                    i = k
                    continue
        i += 1

    tail = text[start:].strip()
    if tail:
        abs_start = text.find(tail, start)
        if abs_start < 0:
            abs_start = start
        parts.append((abs_start, abs_start + len(tail), tail))

    if not parts and text.strip():
        t = text.strip()
        abs_start = text.find(t)
        parts.append((abs_start, abs_start + len(t), t))

    for idx, (s, e, seg) in enumerate(parts):
        sentences.append(
            ScriptSentence(
                id=f"s{idx}",
                index=idx,
                text=seg,
                start_char=s,
                end_char=e,
            )
        )
    return sentences


def split_paragraphs(text: str, sentences: list[ScriptSentence] | None = None) -> list[ScriptParagraph]:
    """Split on blank lines; attach sentence ids that fall inside each paragraph."""
    if not text.strip():
        return []

    paragraphs: list[ScriptParagraph] = []
    # Split on two+ newlines
    chunks = re.split(r"\n\s*\n", text)
    search_from = 0
    for idx, chunk in enumerate(chunks):
        seg = chunk.strip()
        if not seg:
            continue
        abs_start = text.find(seg, search_from)
        if abs_start < 0:
            abs_start = search_from
        abs_end = abs_start + len(seg)
        search_from = abs_end
        sentence_ids: list[str] = []
        if sentences:
            for sent in sentences:
                mid = (sent.start_char + sent.end_char) // 2
                if abs_start <= mid < abs_end or (
                    sent.start_char >= abs_start and sent.end_char <= abs_end
                ):
                    sentence_ids.append(sent.id)
        paragraphs.append(
            ScriptParagraph(
                id=f"p{idx}",
                index=idx,
                text=seg,
                start_char=abs_start,
                end_char=abs_end,
                sentence_ids=sentence_ids,
            )
        )
    return paragraphs
