"""Multi-signal funny moment detection (laughter alone is not enough)."""

from __future__ import annotations

import re
from typing import Any

from config.settings import get_settings
from core.logging import get_logger
from schemas.funny import FunnyMoment, HumorKind
from schemas.moments import DetectedMoment
from tools.moments.context import (
    MomentContext,
    SpeechUnit,
    build_moment_context,
    nearby_scene,
    text_near,
)

logger = get_logger(__name__)

_JOKE_SETUP = re.compile(
    r"\b(why did|knock knock|what do you call|a priest|walks into|bar)\b",
    re.I,
)
_SARCASM = re.compile(
    r"\b(yeah right|sure jan|as if|totally|oh great|wonderful|obviously)\b|"
    r"\bsure\.\.\.|yeah\.\.\.",
    re.I,
)
_AWKWARD = re.compile(
    r"\b(um+|uh+|awkward|cringe|oops|sorry about that|well this is)\b",
    re.I,
)
_MEME = re.compile(
    r"\b(no cap|ratio|based|sus|bruh|lol|lmao|iykyk|touch grass|main character)\b",
    re.I,
)
_UNEXPECTED = re.compile(
    r"\b(wait what|plot twist|never mind|actually|instead|randomly)\b",
    re.I,
)


def detect_funny_moments(
    *,
    transcript: dict[str, Any] | None = None,
    speech_transcript: dict[str, Any] | None = None,
    scenes: dict[str, Any] | None = None,
    audio_analysis: dict[str, Any] | None = None,
    speakers: dict[str, Any] | None = None,
    analysis: dict[str, Any] | None = None,
    context: MomentContext | None = None,
    min_score: float | None = None,
    max_moments: int | None = None,
    setup_window: float | None = None,
    laughter_weight: float | None = None,
) -> list[FunnyMoment]:
    """Detect funny moments with corroboration; laughter alone is rejected."""
    settings = get_settings()
    min_s = float(min_score if min_score is not None else settings.funny_min_humor_score)
    max_n = int(max_moments if max_moments is not None else settings.funny_max_moments)
    window = float(
        setup_window if setup_window is not None else settings.funny_setup_window
    )
    laugh_w = float(
        laughter_weight if laughter_weight is not None else settings.funny_laughter_weight
    )
    min_dur = float(settings.moment_min_duration)

    ctx = context or build_moment_context(
        transcript=transcript,
        speech_transcript=speech_transcript,
        scenes=scenes,
        audio_analysis=audio_analysis,
        speakers=speakers,
        analysis=analysis,
    )

    candidates: list[FunnyMoment] = []

    # 1) Laughter-only: explicitly score low / reject (no other families)
    for hit in ctx.audio_hits:
        if hit.label != "laughter" and "funny" not in hit.tags:
            continue
        if hit.label not in ("laughter",) and "funny" not in hit.tags:
            continue
        # Will only survive if we find corroboration below via unit scan
        # Skip creating laughter-only candidates here

    # 2) Per speech unit: build signal families
    for i, unit in enumerate(ctx.units):
        kinds: list[HumorKind] = []
        families: set[str] = set()
        evidence: list[str] = []
        base = 0.0

        text = unit.text.strip()
        if not text:
            continue

        # Transcript humor family
        if _JOKE_SETUP.search(text):
            kinds.append("joke")
            families.add("transcript")
            base = max(base, 0.45)
            evidence.append(f"transcript:joke_setup@{unit.start:.1f}")
        if _SARCASM.search(text):
            kinds.append("sarcasm")
            families.add("transcript")
            base = max(base, 0.4)
            evidence.append(f"transcript:sarcasm@{unit.start:.1f}")
        if _AWKWARD.search(text):
            kinds.append("awkward")
            families.add("transcript")
            base = max(base, 0.35)
            evidence.append(f"transcript:awkward@{unit.start:.1f}")
        if _MEME.search(text):
            kinds.append("meme_worthy")
            families.add("transcript")
            base = max(base, 0.4)
            evidence.append(f"transcript:meme@{unit.start:.1f}")
        if _UNEXPECTED.search(text):
            kinds.append("unexpected_statement")
            families.add("transcript")
            base = max(base, 0.35)
            evidence.append(f"transcript:unexpected@{unit.start:.1f}")

        words = text.split()
        short_punch = 2 <= len(words) <= 12 and text.endswith(("!", ".", "?"))
        prev = ctx.units[i - 1] if i > 0 else None
        gap_before = (unit.start - prev.end) if prev else 0.0

        # Comedic timing: pause then short line
        timing_hit = False
        pause_near = _pause_before(ctx, unit.start, window=1.5)
        if short_punch and (gap_before >= 0.45 or pause_near):
            kinds.append("punchline")
            kinds.append("comedic_timing")
            families.add("timing")
            timing_hit = True
            base = max(base, 0.5)
            evidence.append(f"timing:punch_after_gap@{unit.start:.1f}")
            if pause_near:
                evidence.append(f"audio:pause@{pause_near:.1f}")

        # Setup in window before punchline
        if short_punch and prev and (unit.start - prev.start) <= window:
            if _JOKE_SETUP.search(prev.text) or len(prev.text.split()) >= 6:
                kinds.append("punchline")
                families.add("timing")
                families.add("transcript")
                base = max(base, 0.55)
                evidence.append(f"transcript:setup@{prev.start:.1f}")
                timing_hit = True

        # Conversational: speaker change + short witty reply
        for ch_start, ch_end, ch_score in ctx.speaker_changes:
            if abs(ch_start - unit.start) < 1.25 and len(words) <= 14:
                kinds.append("conversational")
                families.add("conversational")
                base = max(base, 0.4)
                evidence.append(f"speaker:change@{ch_start:.1f}")
                break

        # Audio boost (never sole family for acceptance unless with reaction+transcript)
        laugh_boost = 0.0
        reaction_near = False
        for hit in ctx.audio_hits:
            mid_u = (unit.start + unit.end) / 2.0
            mid_h = (hit.start + hit.end) / 2.0
            if abs(mid_h - mid_u) > 2.0:
                continue
            if hit.label == "laughter" or "funny" in hit.tags:
                laugh_boost = max(laugh_boost, min(laugh_w, hit.score * laugh_w))
                kinds.append("laughter")
                families.add("audio")
                evidence.append(f"audio:laughter@{hit.start:.1f}")
            if hit.label == "reaction" or "reaction" in hit.tags:
                reaction_near = True
                kinds.append("reaction")
                families.add("audio")
                base = max(base, base + 0.1)
                evidence.append(f"audio:reaction@{hit.start:.1f}")

        # Scene / visual boost
        scene = nearby_scene(ctx, (unit.start + unit.end) / 2.0, window=1.75)
        if scene and any(k in scene.kinds for k in ("cut", "event", "transition")):
            kinds.append("visual_event")
            families.add("visual")
            base = max(base, base + 0.12)
            evidence.append(f"scene:{'/'.join(scene.kinds)}@{scene.start:.1f}")

        # Object cues from analysis (motion hotspot as visual proxy — not faces)
        for cue in _object_cues(analysis):
            if abs(cue - ((unit.start + unit.end) / 2.0)) < 2.0:
                kinds.append("visual_event")
                families.add("visual")
                evidence.append(f"visual:motion_hotspot@{cue:.1f}")
                base = max(base, base + 0.08)
                break

        # Corroboration gate
        strong_punch_timing = timing_hit and ("punchline" in kinds or "joke" in kinds)
        if len(families) < 2 and not strong_punch_timing:
            continue
        # Laughter alone (only audio family)
        if families == {"audio"}:
            continue

        score = min(1.0, base + laugh_boost)
        if reaction_near and "transcript" in families:
            score = min(1.0, score + 0.05)
        if score < min_s:
            continue

        # Dedupe kinds
        uniq_kinds = list(dict.fromkeys(kinds))
        title = text[:48].strip() or "Funny moment"
        explanation = _explain(uniq_kinds, families, laugh_boost > 0)
        end = max(unit.end, unit.start + min_dur)
        candidates.append(
            FunnyMoment(
                start=unit.start,
                end=end,
                category="funny",
                humor_kinds=uniq_kinds,  # type: ignore[arg-type]
                humor_score=score,
                explanation=explanation,
                transcript=text,
                suggested_title=title,
                evidence=evidence,
            )
        )

    # Merge overlapping
    candidates = _merge(candidates, gap=0.75)
    candidates = sorted(candidates, key=lambda m: m.humor_score, reverse=True)[:max_n]
    candidates.sort(key=lambda m: m.start)
    for i, m in enumerate(candidates):
        m.id = i

    logger.info("Funny detect produced %s moments", len(candidates))
    return candidates


def merge_funny_moments_into_detected(
    funny_moments: list[FunnyMoment] | dict[str, Any] | None,
) -> list[DetectedMoment]:
    """Convert FunnyMoment list/report into Highlight DetectedMoment entries."""
    items: list[FunnyMoment] = []
    if funny_moments is None:
        return []
    if isinstance(funny_moments, dict):
        raw = funny_moments.get("moments") or []
        for item in raw:
            if isinstance(item, FunnyMoment):
                items.append(item)
            else:
                items.append(FunnyMoment.model_validate(item))
    else:
        items = list(funny_moments)

    out: list[DetectedMoment] = []
    for m in items:
        out.append(
            DetectedMoment(
                category="funny",
                start=m.start,
                end=m.end,
                title=m.suggested_title or m.transcript[:48],
                reason=m.explanation,
                score=m.humor_score,
                transcript=m.transcript,
                evidence=list(m.evidence),
            )
        )
    return out


def _pause_before(ctx: MomentContext, t: float, window: float) -> float | None:
    for hit in ctx.audio_hits:
        if hit.label not in ("pause", "silence"):
            continue
        if 0 <= t - hit.end <= window or 0 <= t - hit.start <= window:
            return hit.start
    return None


def _object_cues(analysis: dict[str, Any] | None) -> list[float]:
    if not analysis:
        return []
    times: list[float] = []
    for cue in analysis.get("object_cues") or []:
        if cue.get("label") != "motion_hotspot":
            continue
        try:
            times.append(float(cue.get("time_seconds", 0.0)))
        except (TypeError, ValueError):
            continue
    return times


def _explain(kinds: list[str], families: set[str], had_laugh: bool) -> str:
    parts = [f"signals={','.join(sorted(families))}"]
    if kinds:
        parts.append(f"kinds={','.join(kinds)}")
    if had_laugh:
        parts.append("laughter used as boost only (not sole evidence)")
    else:
        parts.append("no laughter required")
    return "; ".join(parts)


def _merge(items: list[FunnyMoment], gap: float) -> list[FunnyMoment]:
    if not items:
        return []
    items = sorted(items, key=lambda m: m.start)
    merged: list[FunnyMoment] = [items[0].model_copy(deep=True)]
    for m in items[1:]:
        cur = merged[-1]
        if m.start <= cur.end + gap:
            cur.end = max(cur.end, m.end)
            if m.humor_score > cur.humor_score:
                cur.humor_score = m.humor_score
                cur.explanation = m.explanation
                cur.suggested_title = m.suggested_title
                cur.transcript = m.transcript or cur.transcript
            for k in m.humor_kinds:
                if k not in cur.humor_kinds:
                    cur.humor_kinds.append(k)
            for e in m.evidence:
                if e not in cur.evidence:
                    cur.evidence.append(e)
        else:
            merged.append(m.model_copy(deep=True))
    return merged
