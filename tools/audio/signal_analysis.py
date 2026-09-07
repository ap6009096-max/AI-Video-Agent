"""Transcript + silence/volume heuristics for scored audio evidence."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from config.settings import get_settings
from core.logging import get_logger
from schemas.audio_speakers import EvidenceTag, ScoredSpan

logger = get_logger(__name__)

_LAUGH_RE = re.compile(
    r"\b(haha|hahaha|hehe|lol|lmao|rofl|laugh(?:ing|s|ed)?|giggle)\b",
    re.IGNORECASE,
)
_QUESTION_START = re.compile(
    r"^(who|what|when|where|why|how|is|are|do|does|did|can|could|would|will|have|has)\b",
    re.IGNORECASE,
)


def analyze_audio_signals(
    *,
    media_path: str | Path | None = None,
    analysis: dict[str, Any] | None = None,
    speech_transcript: dict[str, Any] | None = None,
    transcript: dict[str, Any] | None = None,
    pause_gap: float | None = None,
    volume_spike_db: float | None = None,
    max_events: int | None = None,
) -> dict[str, Any]:
    """Fuse analysis.audio + transcript into scored spans (no ML classifiers)."""
    settings = get_settings()
    gap = float(pause_gap if pause_gap is not None else settings.audio_pause_gap)
    spike_db = float(
        volume_spike_db if volume_spike_db is not None else settings.audio_volume_spike_db
    )
    max_n = int(max_events if max_events is not None else settings.audio_max_events)

    units = _speech_units(speech_transcript, transcript)
    duration = _infer_duration(analysis, units)
    audio = (analysis or {}).get("audio") or {}
    mean_vol = audio.get("mean_volume_db")
    try:
        mean_vol_f = float(mean_vol) if mean_vol is not None else None
    except (TypeError, ValueError):
        mean_vol_f = None

    silence_spans = _silence_spans(audio, duration)
    pause_spans = _pause_spans(units, gap)
    volume_events = _volume_events_from_silence(silence_spans, mean_vol_f, spike_db, duration)
    intensity_spans = _intensity_spans(units, duration)
    laughter = _laughter_candidates(units, volume_events)
    excitement = _excitement_candidates(units, volume_events)
    questions = _question_spans(units)
    reactions = _reaction_spans(units, pause_spans, gap)

    # Cap each list by score
    silence_spans = _cap(silence_spans, max_n)
    pause_spans = _cap(pause_spans, max_n)
    volume_events = _cap(volume_events, max_n)
    intensity_spans = _cap(intensity_spans, max_n)
    laughter = _cap(laughter, max_n)
    excitement = _cap(excitement, max_n)
    questions = _cap(questions, max_n)
    reactions = _cap(reactions, max_n)

    summary = _summary_scores(
        duration=duration,
        silence_spans=silence_spans,
        pause_spans=pause_spans,
        volume_events=volume_events,
        intensity_spans=intensity_spans,
        laughter=laughter,
        excitement=excitement,
        questions=questions,
        reactions=reactions,
        units=units,
    )

    notes = ""
    if not media_path or not Path(str(media_path)).is_file():
        notes = (
            "Transcript-only audio analysis: no local media. "
            "Silence/volume from analysis used when present; FFmpeg re-probe skipped."
        )

    logger.info(
        "Audio signals duration=%.2f pauses=%s questions=%s laughter=%s",
        duration,
        len(pause_spans),
        len(questions),
        len(laughter),
    )
    return {
        "silence_spans": silence_spans,
        "pause_spans": pause_spans,
        "volume_events": volume_events,
        "intensity_spans": intensity_spans,
        "laughter_candidates": laughter,
        "excitement_candidates": excitement,
        "question_spans": questions,
        "reaction_spans": reactions,
        "summary_scores": summary,
        "duration": duration,
        "notes": notes,
    }


def _speech_units(
    speech_transcript: dict[str, Any] | None,
    transcript: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    if speech_transcript:
        for seg in speech_transcript.get("segments") or []:
            try:
                start = float(seg.get("start", 0.0))
                end = float(seg.get("end", start))
            except (TypeError, ValueError):
                continue
            text = str(seg.get("text") or "").strip()
            if end > start:
                units.append({"start": start, "end": end, "text": text})
    elif transcript:
        for sent in transcript.get("sentences") or []:
            try:
                start = float(sent.get("start_seconds") or 0.0)
                end = float(sent.get("end_seconds") or start)
            except (TypeError, ValueError):
                continue
            text = str(sent.get("text") or "").strip()
            if end >= start:
                units.append({"start": start, "end": end, "text": text})
    units.sort(key=lambda u: u["start"])
    return units


def _infer_duration(
    analysis: dict[str, Any] | None, units: list[dict[str, Any]]
) -> float:
    if analysis:
        props = analysis.get("properties") or {}
        try:
            d = float(props.get("duration_seconds") or 0.0)
            if d > 0:
                return d
        except (TypeError, ValueError):
            pass
    if units:
        return max(float(u["end"]) for u in units)
    return 0.0


def _silence_spans(audio: dict[str, Any], duration: float) -> list[ScoredSpan]:
    out: list[ScoredSpan] = []
    for r in audio.get("silence_ranges") or []:
        try:
            start = float(r.get("start", 0.0))
            end = float(r.get("end", start))
        except (TypeError, ValueError):
            continue
        if end <= start:
            continue
        dur = end - start
        score = min(1.0, dur / 3.0)
        out.append(
            ScoredSpan(
                start=start,
                end=end,
                score=score,
                label="silence",
                evidence_tags=["clip_boundary", "emotional"],
                detail=f"silence_duration={dur:.2f}s",
            )
        )
    return out


def _pause_spans(units: list[dict[str, Any]], gap: float) -> list[ScoredSpan]:
    out: list[ScoredSpan] = []
    for i in range(len(units) - 1):
        a, b = units[i], units[i + 1]
        pause = float(b["start"]) - float(a["end"])
        if pause >= gap:
            score = min(1.0, pause / 4.0)
            out.append(
                ScoredSpan(
                    start=float(a["end"]),
                    end=float(b["start"]),
                    score=score,
                    label="pause",
                    evidence_tags=["clip_boundary", "reaction"],
                    detail=f"gap={pause:.2f}s",
                )
            )
    return out


def _volume_events_from_silence(
    silence_spans: list[ScoredSpan],
    mean_vol: float | None,
    spike_db: float,
    duration: float,
) -> list[ScoredSpan]:
    """Treat ends of silence as potential volume rises (proxy without windowed probe)."""
    out: list[ScoredSpan] = []
    for sil in silence_spans:
        t = sil.end
        if duration > 0 and t >= duration:
            continue
        score = min(1.0, 0.4 + sil.score * 0.4)
        if mean_vol is not None and spike_db > 0:
            # Heuristic boost when mean volume is known (presence of measurable audio)
            score = min(1.0, score + 0.1)
        out.append(
            ScoredSpan(
                start=max(0.0, t - 0.15),
                end=t + 0.35,
                score=score,
                label="volume_rise",
                evidence_tags=["viral", "clip_boundary", "reaction"],
                detail=f"after_silence mean_db={mean_vol}",
            )
        )
    return out


def _intensity_spans(units: list[dict[str, Any]], duration: float) -> list[ScoredSpan]:
    out: list[ScoredSpan] = []
    for u in units:
        text = u["text"]
        words = max(1, len(text.split()))
        seg_dur = max(0.05, float(u["end"]) - float(u["start"]))
        wps = words / seg_dur
        score = min(1.0, wps / 5.0)
        if score < 0.35:
            continue
        tags: list[EvidenceTag] = ["viral"] if score >= 0.7 else ["emotional"]
        out.append(
            ScoredSpan(
                start=float(u["start"]),
                end=float(u["end"]),
                score=score,
                label="speech_intensity",
                evidence_tags=tags,
                detail=f"wps={wps:.2f}",
            )
        )
    return out


def _laughter_candidates(
    units: list[dict[str, Any]], volume_events: list[ScoredSpan]
) -> list[ScoredSpan]:
    out: list[ScoredSpan] = []
    for u in units:
        text = u["text"]
        if not _LAUGH_RE.search(text):
            continue
        nearby = any(
            abs(((v.start + v.end) / 2.0) - ((u["start"] + u["end"]) / 2.0)) < 1.5
            for v in volume_events
        )
        score = 0.85 if nearby else 0.65
        out.append(
            ScoredSpan(
                start=float(u["start"]),
                end=float(u["end"]),
                score=score,
                label="laughter",
                evidence_tags=["funny", "reaction"],
                detail="keyword_laughter" + ("+volume" if nearby else ""),
            )
        )
    return out


def _excitement_candidates(
    units: list[dict[str, Any]], volume_events: list[ScoredSpan]
) -> list[ScoredSpan]:
    out: list[ScoredSpan] = []
    for u in units:
        text = u["text"]
        bangs = text.count("!")
        caps_tokens = sum(
            1
            for w in text.split()
            if len(w) >= 3 and w.isupper() and w.isalpha()
        )
        if bangs == 0 and caps_tokens == 0:
            continue
        score = min(1.0, 0.35 + 0.2 * bangs + 0.15 * caps_tokens)
        nearby = any(
            abs(((v.start + v.end) / 2.0) - ((u["start"] + u["end"]) / 2.0)) < 1.0
            for v in volume_events
        )
        if nearby:
            score = min(1.0, score + 0.15)
        out.append(
            ScoredSpan(
                start=float(u["start"]),
                end=float(u["end"]),
                score=score,
                label="excitement",
                evidence_tags=["viral", "emotional", "reaction"],
                detail=f"bangs={bangs} caps={caps_tokens}",
            )
        )
    return out


def _question_spans(units: list[dict[str, Any]]) -> list[ScoredSpan]:
    out: list[ScoredSpan] = []
    for u in units:
        text = u["text"].strip()
        if not text:
            continue
        is_q = text.endswith("?") or bool(_QUESTION_START.match(text))
        if not is_q:
            continue
        out.append(
            ScoredSpan(
                start=float(u["start"]),
                end=float(u["end"]),
                score=0.7 if text.endswith("?") else 0.55,
                label="question",
                evidence_tags=["clip_boundary", "reaction"],
                detail=text[:80],
            )
        )
    return out


def _reaction_spans(
    units: list[dict[str, Any]],
    pause_spans: list[ScoredSpan],
    gap: float,
) -> list[ScoredSpan]:
    out: list[ScoredSpan] = []
    pause_ends = {round(p.end, 2) for p in pause_spans}
    for u in units:
        dur = float(u["end"]) - float(u["start"])
        words = len(str(u["text"]).split())
        near_pause = any(abs(float(u["start"]) - pe) < 0.35 for pe in pause_ends)
        if near_pause and dur <= 2.0 and words <= 8:
            out.append(
                ScoredSpan(
                    start=float(u["start"]),
                    end=float(u["end"]),
                    score=min(1.0, 0.5 + (gap / max(dur, 0.1)) * 0.1),
                    label="reaction",
                    evidence_tags=["reaction", "funny", "clip_boundary"],
                    detail="short_burst_after_pause",
                )
            )
    return out


def _cap(spans: list[ScoredSpan], max_n: int) -> list[ScoredSpan]:
    if len(spans) <= max_n:
        return spans
    return sorted(spans, key=lambda s: s.score, reverse=True)[:max_n]


def _summary_scores(
    *,
    duration: float,
    silence_spans: list[ScoredSpan],
    pause_spans: list[ScoredSpan],
    volume_events: list[ScoredSpan],
    intensity_spans: list[ScoredSpan],
    laughter: list[ScoredSpan],
    excitement: list[ScoredSpan],
    questions: list[ScoredSpan],
    reactions: list[ScoredSpan],
    units: list[dict[str, Any]],
) -> dict[str, float]:
    dur = duration if duration > 0 else 1.0
    silence_dur = sum(max(0.0, s.end - s.start) for s in silence_spans)
    pause_dur = sum(max(0.0, s.end - s.start) for s in pause_spans)
    speech_dur = sum(max(0.0, u["end"] - u["start"]) for u in units)

    def avg(spans: list[ScoredSpan]) -> float:
        if not spans:
            return 0.0
        return sum(s.score for s in spans) / len(spans)

    return {
        "silence_ratio": min(1.0, silence_dur / dur),
        "speech_intensity": avg(intensity_spans),
        "volume_dynamics": avg(volume_events),
        "laughter": avg(laughter) if laughter else 0.0,
        "excitement": avg(excitement) if excitement else 0.0,
        "pause_density": min(1.0, (len(pause_spans) / max(1.0, speech_dur / 10.0)) / 5.0),
        "question_density": min(1.0, len(questions) / max(1, len(units))),
        "reaction_density": min(1.0, len(reactions) / max(1, len(units))),
        "pause_ratio": min(1.0, pause_dur / dur),
    }
