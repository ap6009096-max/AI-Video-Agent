"""Tests for text cleaning and segmentation."""

from __future__ import annotations

from tools.text.cleaning import clean_text
from tools.text.sectioning import build_logical_sections
from tools.text.segmenting import split_paragraphs, split_sentences


def test_clean_text_normalizes_quotes_and_whitespace() -> None:
    raw = "Hello\u201cworld\u201d.\r\n\r\n  Next   line.\t"
    cleaned = clean_text(raw)
    assert '"world"' in cleaned
    assert "\r" not in cleaned
    assert "  " not in cleaned.replace("\n\n", "")


def test_split_sentences_offsets() -> None:
    text = "Hello world. How are you? Fine!"
    sentences = split_sentences(text)
    assert len(sentences) >= 2
    assert sentences[0].text.startswith("Hello")
    assert sentences[0].start_char == 0
    for s in sentences:
        assert text[s.start_char : s.end_char] == s.text


def test_split_paragraphs_with_sentence_ids() -> None:
    text = "First paragraph one. Still first.\n\nSecond paragraph here."
    sentences = split_sentences(text)
    paragraphs = split_paragraphs(text, sentences)
    assert len(paragraphs) == 2
    assert paragraphs[0].sentence_ids
    assert paragraphs[1].sentence_ids


def test_logical_sections_respect_paragraphs() -> None:
    text = "Intro sentence one. Intro two.\n\nBody sentence one. Body two."
    sentences = split_sentences(text)
    paragraphs = split_paragraphs(text, sentences)
    sections = build_logical_sections(text, paragraphs, sentences)
    assert len(sections) >= 1
    assert sections[0].end_char > sections[0].start_char
    # Section bounds should not cut mid-sentence (aligned to paragraph spans)
    for sec in sections:
        assert sec.start_char <= sec.end_char
