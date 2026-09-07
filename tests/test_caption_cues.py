"""Tests for caption cue enrichment."""

from __future__ import annotations

from schemas.captions import CaptionCue, CaptionWord
from tools.captions.cues import enrich_cues_with_words


def test_enrich_attaches_overlapping_words() -> None:
    sentences = [
        CaptionCue(level="sentence", start=0.0, end=2.0, text="Hello viral world", words=[]),
    ]
    words = [
        CaptionCue(
            level="word",
            start=0.0,
            end=0.5,
            text="Hello",
            words=[CaptionWord(word="Hello", start=0.0, end=0.5)],
        ),
        CaptionCue(
            level="word",
            start=0.5,
            end=1.2,
            text="viral",
            words=[CaptionWord(word="viral", start=0.5, end=1.2, highlighted=True)],
        ),
        CaptionCue(
            level="word",
            start=1.2,
            end=2.0,
            text="world",
            words=[CaptionWord(word="world", start=1.2, end=2.0)],
        ),
    ]
    out = enrich_cues_with_words(sentences, words)
    assert len(out[0].words) == 3
    assert out[0].words[0].word == "Hello"


def test_enrich_keeps_existing_words() -> None:
    existing = [
        CaptionWord(word="Hi", start=0.0, end=0.5),
    ]
    sentences = [
        CaptionCue(
            level="sentence",
            start=0.0,
            end=1.0,
            text="Hi",
            words=existing,
        ),
    ]
    words = [
        CaptionCue(
            level="word",
            start=0.0,
            end=1.0,
            text="Nope",
            words=[CaptionWord(word="Nope", start=0.0, end=1.0)],
        ),
    ]
    out = enrich_cues_with_words(sentences, words)
    assert out[0].words[0].word == "Hi"
