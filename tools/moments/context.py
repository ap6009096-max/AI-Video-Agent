"""Shared multi-signal context for moment analyzers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SpeechUnit:
    start: float
    end: float
    text: str


@dataclass
class SceneHit:
    start: float
    end: float
    score: float
    kinds: list[str]
    description: str = ""


@dataclass
class AudioHit:
    start: float
    end: float
    score: float
    label: str
    tags: list[str]
    detail: str = ""


@dataclass
class MomentContext:
    units: list[SpeechUnit] = field(default_factory=list)
    scenes: list[SceneHit] = field(default_factory=list)
    audio_hits: list[AudioHit] = field(default_factory=list)
    speaker_changes: list[tuple[float, float, float]] = field(default_factory=list)
    hooks: list[dict[str, Any]] = field(default_factory=list)
    important: list[dict[str, Any]] = field(default_factory=list)
    duration: float = 0.0


def build_moment_context(
    *,
    transcript: dict[str, Any] | None = None,
    speech_transcript: dict[str, Any] | None = None,
    scenes: dict[str, Any] | None = None,
    audio_analysis: dict[str, Any] | None = None,
    speakers: dict[str, Any] | None = None,
    analysis: dict[str, Any] | None = None,
) -> MomentContext:
    """Fuse pipeline artifacts into one analyzer context."""
    units = _speech_units(speech_transcript, transcript)
    scene_hits = _scenes(scenes)
    audio_hits = _audio_hits(audio_analysis)
    changes = _speaker_changes(speakers)
    hooks, important = _transcript_highlights(transcript)
    duration = _duration(analysis, units, scene_hits)
    return MomentContext(
        units=units,
        scenes=scene_hits,
        audio_hits=audio_hits,
        speaker_changes=changes,
        hooks=hooks,
        important=important,
        duration=duration,
    )


def text_near(ctx: MomentContext, start: float, end: float) -> str:
    parts = [
        u.text
        for u in ctx.units
        if u.end >= start - 0.25 and u.start <= end + 0.25 and u.text
    ]
    return " ".join(parts).strip()


def nearby_scene(ctx: MomentContext, t: float, window: float = 1.5) -> SceneHit | None:
    best: SceneHit | None = None
    best_d = window + 1
    for sc in ctx.scenes:
        mid = (sc.start + sc.end) / 2.0
        d = abs(mid - t)
        if d <= window and d < best_d:
            best = sc
            best_d = d
    return best


def audio_with_tag(ctx: MomentContext, tag: str) -> list[AudioHit]:
    return [h for h in ctx.audio_hits if tag in h.tags or h.label == tag]


def _speech_units(
    speech_transcript: dict[str, Any] | None,
    transcript: dict[str, Any] | None,
) -> list[SpeechUnit]:
    units: list[SpeechUnit] = []
    if speech_transcript:
        for seg in speech_transcript.get("segments") or []:
            try:
                start = float(seg.get("start", 0.0))
                end = float(seg.get("end", start))
            except (TypeError, ValueError):
                continue
            text = str(seg.get("text") or "").strip()
            if end > start:
                units.append(SpeechUnit(start=start, end=end, text=text))
    elif transcript:
        for sent in transcript.get("sentences") or []:
            try:
                start = float(sent.get("start_seconds") or 0.0)
                end = float(sent.get("end_seconds") or start)
            except (TypeError, ValueError):
                continue
            text = str(sent.get("text") or "").strip()
            if end >= start:
                units.append(SpeechUnit(start=start, end=end, text=text))
    units.sort(key=lambda u: u.start)
    return units


def _scenes(scenes: dict[str, Any] | None) -> list[SceneHit]:
    out: list[SceneHit] = []
    if not scenes:
        return out
    for sc in scenes.get("scenes") or []:
        try:
            start = float(sc.get("start", 0.0))
            end = float(sc.get("end", start))
            score = float(sc.get("visual_change_score") or sc.get("score") or 0.0)
        except (TypeError, ValueError):
            continue
        kinds = [str(k) for k in (sc.get("change_kinds") or [])]
        out.append(
            SceneHit(
                start=start,
                end=end,
                score=score,
                kinds=kinds,
                description=str(sc.get("description") or ""),
            )
        )
    return out


def _audio_hits(audio_analysis: dict[str, Any] | None) -> list[AudioHit]:
    if not audio_analysis:
        return []
    keys = (
        "silence_spans",
        "pause_spans",
        "volume_events",
        "intensity_spans",
        "laughter_candidates",
        "excitement_candidates",
        "question_spans",
        "reaction_spans",
    )
    out: list[AudioHit] = []
    for key in keys:
        for span in audio_analysis.get(key) or []:
            try:
                start = float(span.get("start", 0.0))
                end = float(span.get("end", start))
                score = float(span.get("score", 0.0))
            except (TypeError, ValueError):
                continue
            out.append(
                AudioHit(
                    start=start,
                    end=end,
                    score=score,
                    label=str(span.get("label") or key),
                    tags=[str(t) for t in (span.get("evidence_tags") or [])],
                    detail=str(span.get("detail") or ""),
                )
            )
    return out


def _speaker_changes(speakers: dict[str, Any] | None) -> list[tuple[float, float, float]]:
    out: list[tuple[float, float, float]] = []
    if not speakers:
        return out
    for c in speakers.get("speaker_change_candidates") or []:
        try:
            start = float(c.get("start", 0.0))
            end = float(c.get("end", start))
            score = float(c.get("score", 0.0))
        except (TypeError, ValueError):
            continue
        out.append((start, end, score))
    return out


def _transcript_highlights(
    transcript: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not transcript:
        return [], []
    hooks = list(transcript.get("hooks") or [])
    important = list(transcript.get("important_statements") or [])
    return hooks, important


def _duration(
    analysis: dict[str, Any] | None,
    units: list[SpeechUnit],
    scenes: list[SceneHit],
) -> float:
    if analysis:
        props = analysis.get("properties") or {}
        try:
            d = float(props.get("duration_seconds") or 0.0)
            if d > 0:
                return d
        except (TypeError, ValueError):
            pass
    ends = [u.end for u in units] + [s.end for s in scenes]
    return max(ends) if ends else 0.0
