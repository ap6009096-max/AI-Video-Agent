"""Build caption cues from transcript timestamps only (never invent timing)."""

from __future__ import annotations

import re
from typing import Any

from schemas.captions import CaptionCue, CaptionTrack, CaptionWord
from tools.captions.catalog import emoji_map, keyword_boost, keyword_stopwords

_WORD_RE = re.compile(r"[A-Za-z0-9']+")


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _valid_span(start: float | None, end: float | None) -> bool:
    return (
        start is not None
        and end is not None
        and end > start
        and start >= 0
    )


def _tokens(text: str) -> list[str]:
    return _WORD_RE.findall(text or "")


def _highlight_tokens(text: str) -> list[str]:
    stop = keyword_stopwords()
    boost = keyword_boost()
    found: list[str] = []
    for tok in _tokens(text):
        low = tok.lower()
        if low in stop:
            continue
        if low in boost or (len(tok) >= 5 and tok[0].isupper()):
            if tok not in found:
                found.append(tok)
    return found[:8]


def _emoji_for_text(text: str, *, enabled: bool) -> str:
    if not enabled:
        return ""
    mapping = emoji_map()
    for tok in _tokens(text):
        emoji = mapping.get(tok.lower())
        if emoji:
            return emoji
    return ""


def _segment_dicts(speech_transcript: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(speech_transcript, dict):
        return []
    segs = speech_transcript.get("segments") or []
    return [s for s in segs if isinstance(s, dict)]


def build_word_cues(
    speech_transcript: dict[str, Any] | None,
    *,
    emoji_enabled: bool = False,
) -> list[CaptionCue]:
    """Word-level cues from Whisper words — skip entries without real times."""
    cues: list[CaptionCue] = []
    for seg in _segment_dicts(speech_transcript):
        words = seg.get("words") or []
        if not isinstance(words, list):
            continue
        for w in words:
            if not isinstance(w, dict):
                continue
            text = str(w.get("word") or "").strip()
            start = _as_float(w.get("start"))
            end = _as_float(w.get("end"))
            if not text or not _valid_span(start, end):
                continue
            assert start is not None and end is not None
            highlighted = _highlight_tokens(text)
            cues.append(
                CaptionCue(
                    level="word",
                    start=start,
                    end=end,
                    text=text,
                    highlighted_tokens=highlighted,
                    emoji=_emoji_for_text(text, enabled=emoji_enabled),
                    words=[
                        CaptionWord(
                            word=text,
                            start=start,
                            end=end,
                            highlighted=bool(highlighted),
                        )
                    ],
                )
            )
    return cues


def build_sentence_cues(
    speech_transcript: dict[str, Any] | None,
    structured_transcript: dict[str, Any] | None = None,
    *,
    emoji_enabled: bool = False,
) -> list[CaptionCue]:
    """Sentence cues from Whisper segments, else timed structured sentences only."""
    cues: list[CaptionCue] = []
    for seg in _segment_dicts(speech_transcript):
        text = str(seg.get("text") or "").strip()
        start = _as_float(seg.get("start"))
        end = _as_float(seg.get("end"))
        if not text or not _valid_span(start, end):
            continue
        assert start is not None and end is not None
        word_models: list[CaptionWord] = []
        for w in seg.get("words") or []:
            if not isinstance(w, dict):
                continue
            wt = str(w.get("word") or "").strip()
            ws = _as_float(w.get("start"))
            we = _as_float(w.get("end"))
            if not wt or not _valid_span(ws, we):
                continue
            assert ws is not None and we is not None
            hl = bool(_highlight_tokens(wt))
            word_models.append(
                CaptionWord(word=wt, start=ws, end=we, highlighted=hl)
            )
        cues.append(
            CaptionCue(
                level="sentence",
                start=start,
                end=end,
                text=text,
                highlighted_tokens=_highlight_tokens(text),
                emoji=_emoji_for_text(text, enabled=emoji_enabled),
                words=word_models,
            )
        )
    if cues:
        return cues

    # Fallback: structured transcript sentences with real media times only
    if not isinstance(structured_transcript, dict):
        return []
    sentences = structured_transcript.get("sentences") or []
    if not isinstance(sentences, list):
        return []
    for sent in sentences:
        if not isinstance(sent, dict):
            continue
        text = str(sent.get("text") or "").strip()
        start = _as_float(sent.get("start_seconds"))
        end = _as_float(sent.get("end_seconds"))
        if not text or not _valid_span(start, end):
            continue
        assert start is not None and end is not None
        cues.append(
            CaptionCue(
                level="sentence",
                start=start,
                end=end,
                text=text,
                highlighted_tokens=_highlight_tokens(text),
                emoji=_emoji_for_text(text, enabled=emoji_enabled),
            )
        )
    return cues


def build_primary_track(
    *,
    language: str,
    direction: str,
    sentence_cues: list[CaptionCue],
) -> CaptionTrack:
    return CaptionTrack(
        language=language or "",
        direction=direction if direction in ("ltr", "rtl") else "ltr",
        localized=False,
        cues=list(sentence_cues),
    )


def enrich_cues_with_words(
    sentence_cues: list[CaptionCue],
    word_cues: list[CaptionCue],
) -> list[CaptionCue]:
    """Attach overlapping word timings onto sentence cues that lack words.

    Never invents times — only copies from existing word cues.
    """
    if not sentence_cues or not word_cues:
        return list(sentence_cues)

    # Flatten CaptionWord entries from word-level cues
    words: list[CaptionWord] = []
    for wc in word_cues:
        if wc.words:
            words.extend(wc.words)
        elif wc.text and _valid_span(wc.start, wc.end):
            words.append(
                CaptionWord(
                    word=wc.text,
                    start=wc.start,
                    end=wc.end,
                    highlighted=bool(wc.highlighted_tokens),
                )
            )

    if not words:
        return list(sentence_cues)

    enriched: list[CaptionCue] = []
    for cue in sentence_cues:
        if cue.words:
            enriched.append(cue)
            continue
        matched = [
            w
            for w in words
            if w.start < cue.end and w.end > cue.start
        ]
        if not matched:
            enriched.append(cue)
            continue
        # Clamp words to cue span for karaoke duration sanity
        clamped: list[CaptionWord] = []
        for w in matched:
            start = max(w.start, cue.start)
            end = min(w.end, cue.end)
            if end <= start:
                continue
            clamped.append(
                CaptionWord(
                    word=w.word,
                    start=start,
                    end=end,
                    highlighted=w.highlighted,
                )
            )
        enriched.append(
            CaptionCue(
                level=cue.level,
                start=cue.start,
                end=cue.end,
                text=cue.text,
                highlighted_tokens=list(cue.highlighted_tokens),
                emoji=cue.emoji,
                words=clamped,
            )
        )
    return enriched


def _localized_script_lines(localizations: dict[str, Any] | None) -> list[str]:
    if not isinstance(localizations, dict):
        return []
    versions = localizations.get("versions") or []
    if not isinstance(versions, list) or not versions:
        return []
    version = versions[0]
    if not isinstance(version, dict):
        return []
    scripts = version.get("scripts") or []
    if not isinstance(scripts, list):
        return []
    lines: list[str] = []
    for script in scripts:
        if not isinstance(script, dict):
            continue
        text = (
            str(script.get("short_script") or "").strip()
            or str(script.get("caption") or "").strip()
            or str(script.get("hook") or "").strip()
        )
        if text:
            lines.append(text)
    return lines


def build_localized_track(
    sentence_cues: list[CaptionCue],
    localizations: dict[str, Any] | None,
    *,
    language: str,
    direction: str,
    emoji_enabled: bool = False,
) -> tuple[CaptionTrack | None, str]:
    """Sentence-level localized track reusing identical segment timings.

    Returns (track_or_None, note). Never invents new timestamps.
    """
    if not sentence_cues:
        return None, "No timed sentence cues for localization."
    lines = _localized_script_lines(localizations)
    if not lines:
        return None, "No localized scripts available."

    # Prefer 1:1 alignment by index when lengths match
    if len(lines) == len(sentence_cues):
        cues = [
            CaptionCue(
                level="sentence",
                start=src.start,
                end=src.end,
                text=lines[i],
                highlighted_tokens=_highlight_tokens(lines[i]),
                emoji=_emoji_for_text(lines[i], enabled=emoji_enabled),
                words=[],
            )
            for i, src in enumerate(sentence_cues)
        ]
        track = CaptionTrack(
            language=language or "",
            direction=direction if direction in ("ltr", "rtl") else "ltr",
            localized=True,
            cues=cues,
        )
        return track, "Localized sentence track aligned 1:1 with source timings."

    # Soft mismatch: keep source timings, attach concatenated localized text
    # only to the first N cues that have matching lines — never invent times.
    n = min(len(lines), len(sentence_cues))
    if n == 0:
        return None, "Could not align localized text to timed cues."
    cues = [
        CaptionCue(
            level="sentence",
            start=sentence_cues[i].start,
            end=sentence_cues[i].end,
            text=lines[i],
            highlighted_tokens=_highlight_tokens(lines[i]),
            emoji=_emoji_for_text(lines[i], enabled=emoji_enabled),
            words=[],
        )
        for i in range(n)
    ]
    track = CaptionTrack(
        language=language or "",
        direction=direction if direction in ("ltr", "rtl") else "ltr",
        localized=True,
        cues=cues,
    )
    note = (
        f"Localized track partial align ({n} cues); "
        f"source had {len(sentence_cues)} sentences, localization had {len(lines)} lines."
    )
    return track, note


def has_usable_timestamps(
    speech_transcript: dict[str, Any] | None,
    structured_transcript: dict[str, Any] | None = None,
) -> bool:
    if build_sentence_cues(speech_transcript, structured_transcript):
        return True
    if build_word_cues(speech_transcript):
        return True
    return False
