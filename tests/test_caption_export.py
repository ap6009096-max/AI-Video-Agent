"""Tests for SRT / VTT / ASS caption export (Dynamic Caption Engine)."""

from __future__ import annotations

from schemas.captions import CaptionCue, CaptionTrack, CaptionWord
from tools.captions.catalog import (
    clear_caption_cache,
    default_caption_style,
    resolve_caption_style,
    resolve_safe_area,
)
from tools.captions.export import (
    ass_is_useful,
    render_ass,
    render_srt,
    render_vtt,
    style_effects,
)


CUES = [
    CaptionCue(level="sentence", start=0.0, end=1.5, text="Hello world"),
    CaptionCue(level="sentence", start=1.5, end=3.0, text="Second line"),
]

KARAOKE_CUE = CaptionCue(
    level="sentence",
    start=0.0,
    end=1.0,
    text="Hello world",
    highlighted_tokens=["Hello"],
    words=[
        CaptionWord(word="Hello", start=0.0, end=0.4, highlighted=True),
        CaptionWord(word="world", start=0.4, end=1.0),
    ],
)


def test_render_srt() -> None:
    srt = render_srt(CUES)
    assert "1\n" in srt
    assert "00:00:00,000 --> 00:00:01,500" in srt
    assert "Hello world" in srt
    assert "00:00:01,500 --> 00:00:03,000" in srt


def test_render_vtt() -> None:
    vtt = render_vtt(CUES)
    assert vtt.startswith("WEBVTT")
    assert "00:00:00.000 --> 00:00:01.500" in vtt
    assert "Hello world" in vtt


def test_render_ass_includes_safe_margins() -> None:
    clear_caption_cache()
    style = resolve_caption_style("Platform Safe") or default_caption_style()
    safe = resolve_safe_area("TikTok")
    assert safe is not None
    track = CaptionTrack(language="en", cues=CUES)
    ass = render_ass(track, style, safe)
    assert "[Script Info]" in ass
    assert "Dialogue:" in ass
    assert str(safe.margin_v) in ass
    assert "Hello world" in ass


def test_ass_useful_for_burn_in_and_animation() -> None:
    clear_caption_cache()
    minimal = resolve_caption_style("Minimal")
    kinetic = resolve_caption_style("Kinetic")
    assert minimal is not None and kinetic is not None
    assert ass_is_useful(minimal, burn_in=True) is True
    assert ass_is_useful(minimal, burn_in=False) is False
    assert ass_is_useful(kinetic, burn_in=False) is True


def test_tiktok_karaoke_and_bounce() -> None:
    clear_caption_cache()
    style = resolve_caption_style("TikTok")
    assert style is not None
    safe = resolve_safe_area("TikTok")
    assert safe is not None
    track = CaptionTrack(language="en", cues=[KARAOKE_CUE])
    ass = render_ass(track, style, safe)
    assert "\\k" in ass
    assert "\\t(" in ass
    assert "\\fscx" in ass
    assert "Hello" in ass


def test_pop_and_zoom_motion_tags() -> None:
    clear_caption_cache()
    pop = resolve_caption_style("Pop")
    reels = resolve_caption_style("Reels")
    safe = resolve_safe_area("YouTube Shorts")
    assert pop is not None and reels is not None and safe is not None
    track = CaptionTrack(language="en", cues=CUES)
    pop_ass = render_ass(track, pop, safe)
    assert "\\t(" in pop_ass and "\\fscx" in pop_ass
    karaoke_track = CaptionTrack(language="en", cues=[KARAOKE_CUE])
    reels_ass = render_ass(karaoke_track, reels, safe)
    assert "\\k" in reels_ass
    assert "\\fscx80" in reels_ass or "\\t(" in reels_ass


def test_gaming_emoji_in_ass() -> None:
    clear_caption_cache()
    style = resolve_caption_style("Gaming")
    safe = resolve_safe_area("TikTok")
    assert style is not None and safe is not None
    cue = CaptionCue(
        level="sentence",
        start=0.0,
        end=1.0,
        text="epic win",
        emoji="🏆",
    )
    track = CaptionTrack(language="en", cues=[cue])
    ass = render_ass(track, style, safe)
    assert "🏆" in ass
    assert "pop" in style_effects(style) or "bounce" in style_effects(style)
