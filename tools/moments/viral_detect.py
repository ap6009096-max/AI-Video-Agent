"""Multi-dimension viral moment ranking (heuristic — not a virality guarantee)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from config.settings import get_settings
from core.logging import get_logger
from schemas.funny import FunnyMoment
from schemas.moments import DetectedMoment
from schemas.viral import ViralMoment, ViralScoreBreakdown
from tools.moments.context import (
    MomentContext,
    build_moment_context,
    nearby_scene,
    text_near,
)

logger = get_logger(__name__)

WEIGHTS = {
    "hook": 0.20,
    "information": 0.15,
    "emotion": 0.15,
    "humor": 0.15,
    "visual": 0.10,
    "completeness": 0.15,
    "shareability": 0.10,
}

_MEME = re.compile(
    r"\b(no cap|ratio|based|sus|bruh|lol|lmao|iykyk|touch grass|main character)\b",
    re.I,
)
_SARCASM = re.compile(
    r"\b(yeah right|sure jan|as if|totally|oh great|wonderful|obviously)\b",
    re.I,
)
_FILLER = re.compile(r"\b(um+|uh+|like+|you know|basically|literally)\b", re.I)
_QUESTION = re.compile(r"\?|^(what|why|how|who|when|where|do you|did you)\b", re.I)

DISCLAIMER = (
    "Ranking heuristic only — final_score does not guarantee virality or engagement."
)


@dataclass
class _Window:
    start: float
    end: float
    seed: str


def compute_final_score(scores: ViralScoreBreakdown | dict[str, float]) -> float:
    """Weighted final_score from the seven dimension scores."""
    if isinstance(scores, ViralScoreBreakdown):
        vals = {
            "hook": scores.hook,
            "information": scores.information,
            "emotion": scores.emotion,
            "humor": scores.humor,
            "visual": scores.visual,
            "completeness": scores.completeness,
            "shareability": scores.shareability,
        }
    else:
        vals = scores
    total = sum(WEIGHTS[k] * float(vals.get(k, 0.0)) for k in WEIGHTS)
    return min(1.0, max(0.0, total))


def detect_viral_moments(
    *,
    transcript: dict[str, Any] | None = None,
    speech_transcript: dict[str, Any] | None = None,
    scenes: dict[str, Any] | None = None,
    audio_analysis: dict[str, Any] | None = None,
    speakers: dict[str, Any] | None = None,
    analysis: dict[str, Any] | None = None,
    funny_moments: dict[str, Any] | list[Any] | None = None,
    context: MomentContext | None = None,
    min_score: float | None = None,
    max_moments: int | None = None,
    window_pad: float | None = None,
) -> list[ViralMoment]:
    """Detect and rank viral candidate windows with 7-dimension scoring."""
    settings = get_settings()
    min_s = float(
        min_score if min_score is not None else settings.viral_min_final_score
    )
    max_n = int(max_moments if max_moments is not None else settings.viral_max_moments)
    pad = float(window_pad if window_pad is not None else settings.viral_window_pad)
    min_dur = float(settings.moment_min_duration)
    merge_gap = float(settings.moment_merge_gap)

    ctx = context or build_moment_context(
        transcript=transcript,
        speech_transcript=speech_transcript,
        scenes=scenes,
        audio_analysis=audio_analysis,
        speakers=speakers,
        analysis=analysis,
    )
    funny_hits = _parse_funny(funny_moments)

    windows = _candidate_windows(ctx, funny_hits, pad=pad, min_dur=min_dur)
    candidates: list[ViralMoment] = []

    for win in windows:
        scores, evidence = _score_window(ctx, win, funny_hits, analysis)
        final = compute_final_score(scores)
        if final < min_s:
            continue
        text = text_near(ctx, win.start, win.end)
        title = (text[:48].strip() or f"Viral candidate @{win.start:.1f}")
        explanation = (
            f"{DISCLAIMER} "
            f"Weighted final_score={final:.2f} from "
            f"hook={scores.hook:.2f}, information={scores.information:.2f}, "
            f"emotion={scores.emotion:.2f}, humor={scores.humor:.2f}, "
            f"visual={scores.visual:.2f}, completeness={scores.completeness:.2f}, "
            f"shareability={scores.shareability:.2f}."
        )
        candidates.append(
            ViralMoment(
                start=win.start,
                end=max(win.end, win.start + min_dur),
                category="viral",
                scores=scores,
                final_score=final,
                explanation=explanation,
                transcript=text,
                suggested_title=title,
                evidence=evidence,
            )
        )

    candidates = _merge(candidates, gap=merge_gap)
    candidates.sort(key=lambda m: m.final_score, reverse=True)
    candidates = candidates[:max_n]
    for i, m in enumerate(candidates):
        m.rank = i + 1
        m.id = i

    logger.info("Viral detect ranked %s moments", len(candidates))
    return candidates


def merge_viral_moments_into_detected(
    viral_moments: list[ViralMoment] | dict[str, Any] | None,
) -> list[DetectedMoment]:
    """Convert ViralMoment list/report into Highlight DetectedMoment entries."""
    items: list[ViralMoment] = []
    if viral_moments is None:
        return []
    if isinstance(viral_moments, dict):
        raw = viral_moments.get("moments") or []
        for item in raw:
            if isinstance(item, ViralMoment):
                items.append(item)
            else:
                items.append(ViralMoment.model_validate(item))
    else:
        items = list(viral_moments)

    out: list[DetectedMoment] = []
    for m in items:
        out.append(
            DetectedMoment(
                category="viral",
                start=m.start,
                end=m.end,
                title=m.suggested_title or m.transcript[:48],
                reason=m.explanation,
                score=m.final_score,
                transcript=m.transcript,
                evidence=list(m.evidence),
            )
        )
    return out


def _parse_funny(
    funny_moments: dict[str, Any] | list[Any] | None,
) -> list[FunnyMoment]:
    if funny_moments is None:
        return []
    raw = (
        funny_moments.get("moments") or []
        if isinstance(funny_moments, dict)
        else list(funny_moments)
    )
    out: list[FunnyMoment] = []
    for item in raw:
        if isinstance(item, FunnyMoment):
            out.append(item)
        else:
            try:
                out.append(FunnyMoment.model_validate(item))
            except Exception:  # noqa: BLE001
                continue
    return out


def _candidate_windows(
    ctx: MomentContext,
    funny_hits: list[FunnyMoment],
    *,
    pad: float,
    min_dur: float,
) -> list[_Window]:
    seeds: list[_Window] = []

    for hook in ctx.hooks:
        idx = hook.get("sentence_index")
        if idx is None:
            continue
        unit = _unit_at_index(ctx, int(idx))
        if unit:
            seeds.append(
                _Window(
                    start=max(0.0, unit.start - pad * 0.5),
                    end=unit.end + pad,
                    seed="hook",
                )
            )

    for imp in ctx.important:
        idx = imp.get("sentence_index")
        if idx is None:
            continue
        unit = _unit_at_index(ctx, int(idx))
        if unit:
            seeds.append(
                _Window(
                    start=max(0.0, unit.start - pad * 0.5),
                    end=unit.end + pad,
                    seed="important",
                )
            )

    viral_labels = {
        "speech_intensity",
        "volume_rise",
        "excitement",
        "reaction",
        "laughter",
    }
    for hit in ctx.audio_hits:
        if "viral" not in hit.tags and hit.label not in viral_labels:
            continue
        seeds.append(
            _Window(
                start=max(0.0, hit.start - pad),
                end=hit.end + pad,
                seed=f"audio:{hit.label}",
            )
        )

    for fm in funny_hits:
        seeds.append(
            _Window(
                start=max(0.0, fm.start - pad),
                end=fm.end + pad,
                seed="funny",
            )
        )

    for sc in ctx.scenes:
        if not any(k in sc.kinds for k in ("cut", "event", "transition")):
            continue
        mid = (sc.start + sc.end) / 2.0
        if not text_near(ctx, mid - 1.0, mid + 1.0):
            continue
        seeds.append(
            _Window(
                start=max(0.0, sc.start - pad * 0.5),
                end=sc.end + pad,
                seed="scene",
            )
        )

    # Fallback: each short punchy speech unit with intensity-ish neighbors
    if not seeds and ctx.units:
        for u in ctx.units:
            words = u.text.split()
            if 3 <= len(words) <= 20:
                seeds.append(
                    _Window(
                        start=max(0.0, u.start - pad * 0.5),
                        end=u.end + pad,
                        seed="speech",
                    )
                )

    # Normalize duration floor
    out: list[_Window] = []
    for w in seeds:
        end = max(w.end, w.start + min_dur)
        out.append(_Window(start=w.start, end=end, seed=w.seed))
    return _dedupe_windows(out, gap=0.5)


def _unit_at_index(ctx: MomentContext, idx: int):
    if 0 <= idx < len(ctx.units):
        return ctx.units[idx]
    return None


def _dedupe_windows(windows: list[_Window], gap: float) -> list[_Window]:
    if not windows:
        return []
    windows = sorted(windows, key=lambda w: w.start)
    merged: list[_Window] = [windows[0]]
    for w in windows[1:]:
        cur = merged[-1]
        if w.start <= cur.end + gap:
            merged[-1] = _Window(
                start=cur.start,
                end=max(cur.end, w.end),
                seed=cur.seed if cur.seed == w.seed else f"{cur.seed}+{w.seed}",
            )
        else:
            merged.append(w)
    return merged


def _score_window(
    ctx: MomentContext,
    win: _Window,
    funny_hits: list[FunnyMoment],
    analysis: dict[str, Any] | None,
) -> tuple[ViralScoreBreakdown, list[str]]:
    mid = (win.start + win.end) / 2.0
    text = text_near(ctx, win.start, win.end)
    evidence: list[str] = [f"seed:{win.seed}"]
    reasons: dict[str, str] = {}

    # Hook
    hook = 0.0
    for h in ctx.hooks:
        idx = h.get("sentence_index")
        unit = _unit_at_index(ctx, int(idx)) if idx is not None else None
        if unit and unit.end >= win.start and unit.start <= win.end:
            hook = max(hook, float(h.get("score") or 0.7))
            evidence.append(f"transcript:hook@{unit.start:.1f}")
    if _QUESTION.search(text or ""):
        hook = max(hook, 0.45)
        evidence.append("transcript:question")
    if win.start < 8.0 and text:
        hook = max(hook, 0.4)
    reasons["hook"] = (
        f"hook={hook:.2f}: transcript hooks/opener energy"
        if hook > 0
        else "hook=0.00: no hook/opener signal"
    )

    # Information
    information = 0.0
    for imp in ctx.important:
        idx = imp.get("sentence_index")
        unit = _unit_at_index(ctx, int(idx)) if idx is not None else None
        if unit and unit.end >= win.start and unit.start <= win.end:
            information = max(information, float(imp.get("score") or 0.65))
            evidence.append(f"transcript:important@{unit.start:.1f}")
    words = (text or "").split()
    if len(words) >= 12:
        information = max(information, 0.4)
    filler_n = len(_FILLER.findall(text or ""))
    if words and filler_n / max(1, len(words)) < 0.08 and len(words) >= 8:
        information = max(information, 0.35)
    reasons["information"] = (
        f"information={information:.2f}: important/dense speech"
        if information > 0
        else "information=0.00: low informational density"
    )

    # Emotion
    emotion = 0.0
    for hit in ctx.audio_hits:
        if abs(((hit.start + hit.end) / 2.0) - mid) > 2.5:
            continue
        if (
            hit.label in ("speech_intensity", "excitement", "reaction", "volume_rise")
            or "emotional" in hit.tags
            or "reaction" in hit.tags
        ):
            emotion = max(emotion, min(1.0, hit.score))
            evidence.append(f"audio:{hit.label}@{hit.start:.1f}")
    reasons["emotion"] = (
        f"emotion={emotion:.2f}: intensity/reaction audio"
        if emotion > 0
        else "emotion=0.00: no emotional audio tags"
    )

    # Humor (funny report preferred; never laughter alone)
    humor = 0.0
    for fm in funny_hits:
        if abs(((fm.start + fm.end) / 2.0) - mid) <= 3.0:
            humor = max(humor, float(fm.humor_score))
            evidence.append(f"funny:humor_score@{fm.start:.1f}")
    if humor == 0.0:
        if _MEME.search(text or "") or _SARCASM.search(text or ""):
            humor = 0.35
            evidence.append("transcript:light_humor_cue")
    reasons["humor"] = (
        f"humor={humor:.2f}: funny agent / light humor cues"
        if humor > 0
        else "humor=0.00: no corroborated humor (laughter alone ignored)"
    )

    # Visual
    visual = 0.0
    scene = nearby_scene(ctx, mid, window=2.0)
    if scene and any(k in scene.kinds for k in ("cut", "event", "transition")):
        visual = max(visual, min(1.0, 0.45 + scene.score * 0.4))
        evidence.append(f"scene:{'/'.join(scene.kinds)}@{scene.start:.1f}")
    for cue_t in _object_cues(analysis):
        if abs(cue_t - mid) < 2.5:
            visual = max(visual, 0.4)
            evidence.append(f"visual:motion_hotspot@{cue_t:.1f}")
            break
    reasons["visual"] = (
        f"visual={visual:.2f}: scene/motion support"
        if visual > 0
        else "visual=0.00: no visual change near window"
    )

    # Completeness
    dur = max(0.0, win.end - win.start)
    completeness = 0.0
    if 3.0 <= dur <= 45.0:
        completeness = 0.55
    elif 1.5 <= dur < 3.0 or 45.0 < dur <= 60.0:
        completeness = 0.35
    else:
        completeness = 0.15
    speech_cov = len(text.split()) if text else 0
    if speech_cov >= 5:
        completeness = min(1.0, completeness + 0.2)
    edge_clear = False
    for hit in ctx.audio_hits:
        if hit.label in ("pause", "silence") and (
            abs(hit.end - win.start) < 1.0 or abs(hit.start - win.end) < 1.0
        ):
            edge_clear = True
            evidence.append(f"audio:boundary_{hit.label}@{hit.start:.1f}")
            break
    for ch_start, ch_end, _ in ctx.speaker_changes:
        if abs(ch_start - win.start) < 1.25 or abs(ch_start - win.end) < 1.25:
            edge_clear = True
            evidence.append(f"speaker:boundary@{ch_start:.1f}")
            break
    if edge_clear:
        completeness = min(1.0, completeness + 0.2)
    reasons["completeness"] = (
        f"completeness={completeness:.2f}: duration={dur:.1f}s, "
        f"speech_words={speech_cov}, clear_edges={edge_clear}"
    )

    # Shareability
    shareability = 0.0
    if text and len(words) <= 18 and len(words) >= 3:
        shareability = max(shareability, 0.4)
    if _MEME.search(text or ""):
        shareability = max(shareability, 0.55)
        evidence.append("transcript:meme_phrasing")
    if emotion >= 0.5 and dur <= 20.0:
        shareability = max(shareability, 0.5)
    if humor >= 0.5 and dur <= 25.0:
        shareability = max(shareability, 0.55)
    if emotion >= 0.6 and visual >= 0.4:
        shareability = max(shareability, 0.6)
    reasons["shareability"] = (
        f"shareability={shareability:.2f}: punchy/meme/reaction window"
        if shareability > 0
        else "shareability=0.00: weak shareability cues"
    )

    breakdown = ViralScoreBreakdown(
        hook=min(1.0, hook),
        information=min(1.0, information),
        emotion=min(1.0, emotion),
        humor=min(1.0, humor),
        visual=min(1.0, visual),
        completeness=min(1.0, completeness),
        shareability=min(1.0, shareability),
        reasons=reasons,
    )
    return breakdown, evidence


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


def _merge(items: list[ViralMoment], gap: float) -> list[ViralMoment]:
    if not items:
        return []
    items = sorted(items, key=lambda m: m.start)
    merged: list[ViralMoment] = [items[0].model_copy(deep=True)]
    for m in items[1:]:
        cur = merged[-1]
        if m.start <= cur.end + gap:
            cur.end = max(cur.end, m.end)
            if m.final_score > cur.final_score:
                cur.final_score = m.final_score
                cur.scores = m.scores
                cur.explanation = m.explanation
                cur.suggested_title = m.suggested_title
                cur.transcript = m.transcript or cur.transcript
            for e in m.evidence:
                if e not in cur.evidence:
                    cur.evidence.append(e)
        else:
            merged.append(m.model_copy(deep=True))
    return merged
