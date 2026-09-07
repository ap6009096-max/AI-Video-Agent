"""Boundary-based smart clip selection (never fixed arbitrary chunks)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from config.settings import get_settings
from core.logging import get_logger
from schemas.clips import ClipCandidate

logger = get_logger(__name__)

# Score blend weights (explicit)
W_SEED = 0.30
W_HOOK = 0.15
W_BOUNDARY = 0.15
W_DURATION = 0.20
W_DENSITY = 0.15
W_SILENCE_PENALTY = 0.05

_TERMINAL = re.compile(r"[.!?…][\"')\]]*\s*$")
_FILLER_ONLY = re.compile(r"^(um+|uh+|like|you know|okay|ok|so|and|but)[.!,?\s]*$", re.I)
_QUESTION = re.compile(r"\?|^(what|why|how|who|when|where|do you|did you)\b", re.I)


@dataclass
class _Sentence:
    start: float
    end: float
    text: str
    sid: str = ""


@dataclass
class _Seed:
    start: float
    end: float
    score: float
    category: str
    title: str = ""
    hook: str = ""
    reason: str = ""
    source: str = ""


@dataclass
class _Timeline:
    sentences: list[_Sentence] = field(default_factory=list)
    seeds: list[_Seed] = field(default_factory=list)
    scene_cuts: list[float] = field(default_factory=list)
    speaker_cuts: list[float] = field(default_factory=list)
    soft_cuts: list[float] = field(default_factory=list)
    silence: list[tuple[float, float]] = field(default_factory=list)
    intensity: list[tuple[float, float, float]] = field(default_factory=list)
    hooks: list[tuple[float, float, str, float]] = field(default_factory=list)
    duration: float = 0.0


def select_smart_clips(
    *,
    transcript: dict[str, Any] | None = None,
    speech_transcript: dict[str, Any] | None = None,
    scenes: dict[str, Any] | None = None,
    audio_analysis: dict[str, Any] | None = None,
    speakers: dict[str, Any] | None = None,
    moments: dict[str, Any] | None = None,
    funny_moments: dict[str, Any] | None = None,
    viral_moments: dict[str, Any] | None = None,
    analysis: dict[str, Any] | None = None,
    target_duration: float | int | None = None,
    duration_tolerance: float | None = None,
    max_clips: int | None = None,
    max_overlap: float | None = None,
    min_score: float | None = None,
) -> list[ClipCandidate]:
    """Select clips from natural boundaries and moment seeds — never fixed tiles."""
    settings = get_settings()
    target = float(
        target_duration
        if target_duration is not None
        else settings.clip_target_duration
    )
    tol = float(
        duration_tolerance
        if duration_tolerance is not None
        else settings.clip_duration_tolerance
    )
    max_n = int(max_clips if max_clips is not None else settings.clip_max_clips)
    max_iou = float(max_overlap if max_overlap is not None else settings.clip_max_overlap)
    min_s = float(min_score if min_score is not None else settings.clip_min_score)

    tl = _build_timeline(
        transcript=transcript,
        speech_transcript=speech_transcript,
        scenes=scenes,
        audio_analysis=audio_analysis,
        speakers=speakers,
        moments=moments,
        funny_moments=funny_moments,
        viral_moments=viral_moments,
        analysis=analysis,
    )
    if not tl.sentences:
        logger.info("Smart clip: no timed sentences — empty result")
        return []

    candidates: list[ClipCandidate] = []
    for seed in tl.seeds:
        cand = _window_from_seed(tl, seed, target=target, tol=tol)
        if cand is not None:
            candidates.append(cand)

    # Story-boundary candidates when seeds are sparse
    if len(candidates) < 3:
        for cut in sorted(set(tl.scene_cuts + tl.soft_cuts))[:12]:
            fake = _Seed(
                start=max(0.0, cut - target * 0.25),
                end=cut + target * 0.25,
                score=0.4,
                category="story",
                source="story_boundary",
            )
            cand = _window_from_seed(tl, fake, target=target, tol=tol)
            if cand is not None:
                candidates.append(cand)

    scored = [_score_candidate(tl, c, target=target) for c in candidates]
    scored = [c for c in scored if c.score >= min_s]
    scored.sort(key=lambda c: c.score, reverse=True)
    selected = _greedy_select(scored, max_n=max_n, max_iou=max_iou)

    for i, c in enumerate(selected):
        c.id = i
        if c.duration <= 0:
            c.duration = max(0.0, c.end - c.start)

    logger.info(
        "Smart clip selected %s clips (from %s candidates) target=%ss",
        len(selected),
        len(scored),
        target,
    )
    return selected


def select_multi_duration_clips(
    *,
    transcript: dict[str, Any] | None = None,
    speech_transcript: dict[str, Any] | None = None,
    scenes: dict[str, Any] | None = None,
    audio_analysis: dict[str, Any] | None = None,
    speakers: dict[str, Any] | None = None,
    moments: dict[str, Any] | None = None,
    funny_moments: dict[str, Any] | None = None,
    viral_moments: dict[str, Any] | None = None,
    analysis: dict[str, Any] | None = None,
    documentary_pack: dict[str, Any] | None = None,
    director_pack: dict[str, Any] | None = None,
    short_durations: list[int] | None = None,
    duration_tolerance: float | None = None,
    max_per_duration: int | None = None,
    max_overlap: float | None = None,
    min_score: float | None = None,
) -> list[ClipCandidate]:
    """Select clips for each requested Short duration; prefer non-overlapping windows."""
    settings = get_settings()
    durations = [
        int(d)
        for d in (short_durations or [10, 40, 90])
        if int(d) > 0
    ]
    if not durations:
        durations = [10, 40, 90]
    # Prefer longer first so shorter clips fill remaining gaps
    durations = sorted(set(durations), reverse=True)

    tol = float(
        duration_tolerance
        if duration_tolerance is not None
        else settings.clip_duration_tolerance
    )
    per = int(
        max_per_duration
        if max_per_duration is not None
        else getattr(settings, "shorts_max_per_duration", 3)
    )
    max_iou = float(max_overlap if max_overlap is not None else settings.clip_max_overlap)
    min_s = float(min_score if min_score is not None else settings.clip_min_score)

    ranking_hints = _ranking_hints(documentary_pack, director_pack)

    selected: list[ClipCandidate] = []
    for target in durations:
        batch = select_smart_clips(
            transcript=transcript,
            speech_transcript=speech_transcript,
            scenes=scenes,
            audio_analysis=audio_analysis,
            speakers=speakers,
            moments=moments,
            funny_moments=funny_moments,
            viral_moments=viral_moments,
            analysis=analysis,
            target_duration=target,
            duration_tolerance=tol,
            max_clips=max(per * 4, per),
            max_overlap=max_iou,
            min_score=min_s,
        )
        kept_for_duration = 0
        for cand in batch:
            if any(_iou(cand, k) > max_iou for k in selected):
                continue
            boosted = _apply_ranking_hints(cand, ranking_hints)
            boosted.target_duration = float(target)
            signals = list(boosted.source_signals or [])
            for ev in boosted.evidence:
                if ev.startswith("seed:") or ev.startswith("category:"):
                    tag = ev.split(":", 1)[-1]
                    if tag and tag not in signals:
                        signals.append(tag)
            if "multi_duration" not in signals:
                signals.append("multi_duration")
            boosted.source_signals = signals
            boosted.evidence = list(boosted.evidence) + [f"target_duration:{target}"]
            selected.append(boosted)
            kept_for_duration += 1
            if kept_for_duration >= per:
                break

    selected.sort(key=lambda c: (c.target_duration, -c.score))
    for i, c in enumerate(selected):
        c.id = i
        if c.duration <= 0:
            c.duration = max(0.0, c.end - c.start)

    logger.info(
        "Multi-duration shorts selected %s clips across durations=%s",
        len(selected),
        durations,
    )
    return selected


def _ranking_hints(
    documentary_pack: dict[str, Any] | None,
    director_pack: dict[str, Any] | None,
) -> list[str]:
    hints: list[str] = []
    if isinstance(documentary_pack, dict):
        plan = documentary_pack.get("plan") or {}
        if isinstance(plan, dict) and not plan.get("skipped"):
            intro = str(plan.get("introduction") or "").strip()
            if intro:
                hints.append(intro.lower())
            for ch in plan.get("chapters") or []:
                if isinstance(ch, dict):
                    for key in ("title", "summary", "narration", "evidence"):
                        bit = str(ch.get(key) or "").strip().lower()
                        if bit:
                            hints.append(bit)
            for line in plan.get("research_structure") or []:
                bit = str(line or "").strip().lower()
                if bit:
                    hints.append(bit)
    if isinstance(director_pack, dict):
        plan = director_pack.get("plan") or {}
        if isinstance(plan, dict) and not plan.get("skipped"):
            for note in plan.get("continuity_notes") or []:
                bit = str(note or "").strip().lower()
                if bit:
                    hints.append(bit)
    return hints[:40]


def _apply_ranking_hints(
    cand: ClipCandidate, hints: list[str]
) -> ClipCandidate:
    if not hints:
        return cand
    text = (cand.transcript or "").lower()
    if not text:
        return cand
    hits = 0
    for hint in hints:
        # Use a short token from each hint
        token = " ".join(hint.split()[:4])
        if len(token) >= 4 and token in text:
            hits += 1
    if hits <= 0:
        return cand
    boost = min(0.12, 0.03 * hits)
    data = cand.model_dump()
    data["score"] = min(1.0, float(cand.score) + boost)
    signals = list(cand.source_signals or [])
    if "documentary_hint" not in signals:
        signals.append("documentary_hint")
    data["source_signals"] = signals
    data["evidence"] = list(cand.evidence) + [f"hint_hits:{hits}"]
    return ClipCandidate.model_validate(data)


def _build_timeline(
    *,
    transcript: dict[str, Any] | None,
    speech_transcript: dict[str, Any] | None,
    scenes: dict[str, Any] | None,
    audio_analysis: dict[str, Any] | None,
    speakers: dict[str, Any] | None,
    moments: dict[str, Any] | None,
    funny_moments: dict[str, Any] | None,
    viral_moments: dict[str, Any] | None,
    analysis: dict[str, Any] | None,
) -> _Timeline:
    tl = _Timeline()
    tl.sentences = _sentences(transcript, speech_transcript)
    if tl.sentences:
        tl.duration = max(s.end for s in tl.sentences)
    if analysis:
        props = analysis.get("properties") or {}
        try:
            d = float(props.get("duration_seconds") or 0.0)
            if d > tl.duration:
                tl.duration = d
        except (TypeError, ValueError):
            pass

    # Seeds from moments / funny / viral
    for item in (moments or {}).get("moments") or []:
        try:
            start = float(item.get("start", 0.0))
            end = float(item.get("end", start))
            score = float(item.get("score", 0.5))
        except (TypeError, ValueError):
            continue
        tl.seeds.append(
            _Seed(
                start=start,
                end=end,
                score=score,
                category=str(item.get("category") or "important"),
                title=str(item.get("title") or ""),
                hook=str(item.get("title") or item.get("transcript") or "")[:80],
                reason=str(item.get("reason") or ""),
                source="moments",
            )
        )
    for item in (funny_moments or {}).get("moments") or []:
        try:
            start = float(item.get("start", 0.0))
            end = float(item.get("end", start))
            score = float(item.get("humor_score", 0.5))
        except (TypeError, ValueError):
            continue
        tl.seeds.append(
            _Seed(
                start=start,
                end=end,
                score=score,
                category="funny",
                title=str(item.get("suggested_title") or ""),
                hook=str(item.get("suggested_title") or item.get("transcript") or "")[:80],
                reason=str(item.get("explanation") or ""),
                source="funny",
            )
        )
    for item in (viral_moments or {}).get("moments") or []:
        try:
            start = float(item.get("start", 0.0))
            end = float(item.get("end", start))
            score = float(item.get("final_score", 0.5))
        except (TypeError, ValueError):
            continue
        scores = item.get("scores") or {}
        hook_txt = ""
        if isinstance(scores, dict) and float(scores.get("hook") or 0) > 0.3:
            hook_txt = str(item.get("suggested_title") or item.get("transcript") or "")[:80]
        tl.seeds.append(
            _Seed(
                start=start,
                end=end,
                score=score,
                category="viral",
                title=str(item.get("suggested_title") or ""),
                hook=hook_txt or str(item.get("suggested_title") or "")[:80],
                reason=str(item.get("explanation") or ""),
                source="viral",
            )
        )

    # Hooks from transcript
    sent_by_id = {s.sid: s for s in tl.sentences if s.sid}
    for hook in (transcript or {}).get("hooks") or []:
        sid = str(hook.get("sentence_id") or "")
        sent = sent_by_id.get(sid)
        if not sent:
            # sentence_index fallback
            idx = hook.get("sentence_index")
            if isinstance(idx, int) and 0 <= idx < len(tl.sentences):
                sent = tl.sentences[idx]
        if sent:
            tl.hooks.append(
                (
                    sent.start,
                    sent.end,
                    str(hook.get("text") or sent.text),
                    float(hook.get("score") or 0.7),
                )
            )
            tl.seeds.append(
                _Seed(
                    start=sent.start,
                    end=sent.end,
                    score=float(hook.get("score") or 0.65),
                    category="important",
                    title=str(hook.get("text") or sent.text)[:48],
                    hook=str(hook.get("text") or sent.text)[:80],
                    reason=str(hook.get("reason") or "hook"),
                    source="hook",
                )
            )

    for imp in (transcript or {}).get("important_statements") or []:
        sid = str(imp.get("sentence_id") or "")
        sent = sent_by_id.get(sid)
        if sent:
            tl.seeds.append(
                _Seed(
                    start=sent.start,
                    end=sent.end,
                    score=0.6,
                    category="important",
                    title=str(imp.get("text") or sent.text)[:48],
                    hook=str(imp.get("text") or sent.text)[:80],
                    reason=str(imp.get("reason") or "important"),
                    source="important",
                )
            )

    # Clip boundaries as soft cuts
    for b in (transcript or {}).get("clip_boundaries") or []:
        sid = str(b.get("after_sentence_id") or "")
        sent = sent_by_id.get(sid)
        if sent:
            tl.soft_cuts.append(sent.end)

    # Section edges
    id_to_sent = {s.sid: s for s in tl.sentences if s.sid}
    for sec in (transcript or {}).get("sections") or []:
        sids = sec.get("sentence_ids") or []
        if not sids:
            continue
        first = id_to_sent.get(str(sids[0]))
        last = id_to_sent.get(str(sids[-1]))
        if first:
            tl.soft_cuts.append(first.start)
        if last:
            tl.soft_cuts.append(last.end)

    for sc in (scenes or {}).get("scenes") or []:
        try:
            start = float(sc.get("start", 0.0))
            end = float(sc.get("end", start))
        except (TypeError, ValueError):
            continue
        kinds = [str(k) for k in (sc.get("change_kinds") or [])]
        if any(k in kinds for k in ("cut", "transition", "event")):
            tl.scene_cuts.extend([start, end])
        else:
            tl.soft_cuts.extend([start, end])

    for ch in (speakers or {}).get("speaker_change_candidates") or []:
        try:
            tl.speaker_cuts.append(float(ch.get("start", 0.0)))
        except (TypeError, ValueError):
            continue

    for key in ("silence_spans", "pause_spans"):
        for span in (audio_analysis or {}).get(key) or []:
            try:
                s = float(span.get("start", 0.0))
                e = float(span.get("end", s))
            except (TypeError, ValueError):
                continue
            tl.silence.append((s, e))
            tl.soft_cuts.append((s + e) / 2.0)

    for key in ("intensity_spans", "volume_events", "excitement_candidates"):
        for span in (audio_analysis or {}).get(key) or []:
            try:
                s = float(span.get("start", 0.0))
                e = float(span.get("end", s))
                sc = float(span.get("score", 0.5))
            except (TypeError, ValueError):
                continue
            tl.intensity.append((s, e, sc))

    return tl


def _sentences(
    transcript: dict[str, Any] | None,
    speech_transcript: dict[str, Any] | None,
) -> list[_Sentence]:
    out: list[_Sentence] = []
    if transcript:
        for sent in transcript.get("sentences") or []:
            try:
                start = sent.get("start_seconds")
                end = sent.get("end_seconds")
                if start is None or end is None:
                    continue
                start_f = float(start)
                end_f = float(end)
            except (TypeError, ValueError):
                continue
            text = str(sent.get("text") or "").strip()
            if end_f > start_f and text:
                out.append(
                    _Sentence(
                        start=start_f,
                        end=end_f,
                        text=text,
                        sid=str(sent.get("id") or ""),
                    )
                )
    if out:
        out.sort(key=lambda s: s.start)
        return out

    # Fallback: speech segments as pseudo-sentences
    if speech_transcript:
        for i, seg in enumerate(speech_transcript.get("segments") or []):
            try:
                start_f = float(seg.get("start", 0.0))
                end_f = float(seg.get("end", start_f))
            except (TypeError, ValueError):
                continue
            text = str(seg.get("text") or "").strip()
            if end_f > start_f and text:
                out.append(
                    _Sentence(
                        start=start_f,
                        end=end_f,
                        text=text,
                        sid=f"seg{i}",
                    )
                )
    out.sort(key=lambda s: s.start)
    return out


def _window_from_seed(
    tl: _Timeline,
    seed: _Seed,
    *,
    target: float,
    tol: float,
) -> ClipCandidate | None:
    """Grow a window around a seed, snapped to sentence boundaries."""
    if not tl.sentences:
        return None
    mid = (seed.start + seed.end) / 2.0
    # Prefer left-align from seed start for hooks; else center
    if seed.source in ("hook", "important"):
        ideal_start = seed.start
        ideal_end = seed.start + target
    else:
        ideal_start = mid - target / 2.0
        ideal_end = mid + target / 2.0

    start = _snap_start(tl.sentences, ideal_start)
    end = _snap_end(tl.sentences, ideal_end)
    if start is None or end is None or end <= start:
        return None

    start, end = _trim_silence(tl, start, end)
    if end <= start:
        return None

    duration = end - start
    lo = target * (1.0 - tol)
    hi = target * (1.0 + tol)
    # Expand/shrink by snapping more sentences if far from band
    if duration < lo:
        end2 = _snap_end(tl.sentences, start + target)
        if end2 and end2 > end:
            end = end2
            duration = end - start
    if duration > hi:
        # Prefer shrinking end toward target while staying on sentence end
        end2 = _snap_end(tl.sentences, start + target)
        if end2 and end2 > start:
            end = end2
            duration = end - start

    if duration < lo * 0.85 or duration > hi * 1.15:
        return None

    text = _text_between(tl.sentences, start, end)
    if not text or _FILLER_ONLY.match(text.strip()):
        return None
    # Incomplete thought: last sentence should look finished
    last = _last_sentence_in(tl.sentences, start, end)
    if last and not _TERMINAL.search(last.text.strip()) and len(last.text.split()) > 4:
        # try extend to next sentence end once
        nxt = _next_sentence_after(tl.sentences, last.end)
        if nxt:
            end = nxt.end
            duration = end - start
            text = _text_between(tl.sentences, start, end)
            if duration > hi * 1.2:
                return None

    # Reject mid-sentence: start/end must equal some sentence bounds
    if not _is_sentence_start(tl.sentences, start):
        return None
    if not _is_sentence_end(tl.sentences, end):
        return None

    silence_ratio = _silence_ratio(tl, start, end)
    if silence_ratio > 0.45:
        return None

    hook = seed.hook or (text.split(".")[0][:80] if text else "")
    evidence = [f"seed:{seed.source}", f"category:{seed.category}"]
    return ClipCandidate(
        start=start,
        end=end,
        duration=duration,
        transcript=text,
        category=seed.category or "story",
        score=0.0,  # filled later
        hook=hook,
        reason=seed.reason or f"Boundary-snapped clip from {seed.source}",
        title=seed.title or hook[:48],
        evidence=evidence,
        target_duration=float(target),
        source_signals=[seed.source, seed.category] if seed.source else [seed.category],
    )


def _snap_start(sentences: list[_Sentence], t: float) -> float | None:
    """Nearest sentence start at or before t (never mid-sentence)."""
    best: float | None = None
    for s in sentences:
        if s.start <= t + 1e-6:
            best = s.start
        else:
            break
    if best is None and sentences:
        # If t is before first sentence, use first start only if close
        if abs(sentences[0].start - t) < 2.0:
            return sentences[0].start
    return best


def _snap_end(sentences: list[_Sentence], t: float) -> float | None:
    """Nearest sentence end at or after t (never mid-sentence)."""
    best: float | None = None
    for s in sentences:
        if s.end >= t - 1e-6:
            best = s.end
            break
    if best is None and sentences:
        return sentences[-1].end
    return best


def _is_sentence_start(sentences: list[_Sentence], t: float) -> bool:
    return any(abs(s.start - t) < 1e-3 for s in sentences)


def _is_sentence_end(sentences: list[_Sentence], t: float) -> bool:
    return any(abs(s.end - t) < 1e-3 for s in sentences)


def _text_between(sentences: list[_Sentence], start: float, end: float) -> str:
    parts = [
        s.text
        for s in sentences
        if s.start >= start - 1e-3 and s.end <= end + 1e-3
    ]
    return " ".join(parts).strip()


def _last_sentence_in(
    sentences: list[_Sentence], start: float, end: float
) -> _Sentence | None:
    last = None
    for s in sentences:
        if s.start >= start - 1e-3 and s.end <= end + 1e-3:
            last = s
    return last


def _next_sentence_after(sentences: list[_Sentence], t: float) -> _Sentence | None:
    for s in sentences:
        if s.start >= t - 1e-3:
            return s
    return None


def _trim_silence(tl: _Timeline, start: float, end: float) -> tuple[float, float]:
    """Trim leading/trailing silence while staying on sentence bounds."""
    s, e = start, end
    for sil_s, sil_e in tl.silence:
        # Leading silence overlapping start
        if sil_s <= s + 0.15 and sil_e > s and sil_e < e - 1.0:
            snapped = _snap_start(tl.sentences, sil_e)
            if snapped is not None and snapped < e:
                s = snapped
        # Trailing silence overlapping end
        if sil_e >= e - 0.15 and sil_s < e and sil_s > s + 1.0:
            snapped = _snap_end(tl.sentences, sil_s)
            if snapped is not None and snapped > s:
                e = snapped
    return s, e


def _silence_ratio(tl: _Timeline, start: float, end: float) -> float:
    dur = max(1e-6, end - start)
    covered = 0.0
    for s, e in tl.silence:
        a = max(s, start)
        b = min(e, end)
        if b > a:
            covered += b - a
    return min(1.0, covered / dur)


def _score_candidate(
    tl: _Timeline, cand: ClipCandidate, *, target: float
) -> ClipCandidate:
    """Blend seed/hook/boundary/duration/density with silence penalty."""
    start, end = cand.start, cand.end
    evidence = list(cand.evidence)

    # Seed overlap strength
    seed_score = 0.0
    best_cat = cand.category
    for seed in tl.seeds:
        if seed.end < start or seed.start > end:
            continue
        overlap = min(seed.end, end) - max(seed.start, start)
        if overlap <= 0:
            continue
        seed_score = max(seed_score, seed.score)
        if seed.score >= seed_score:
            best_cat = seed.category
            if seed.hook:
                cand.hook = seed.hook
    if seed_score > 0:
        evidence.append(f"seed_score:{seed_score:.2f}")

    # Hook presence
    hook_score = 0.0
    for hs, he, htext, hsc in tl.hooks:
        if he >= start and hs <= end:
            hook_score = max(hook_score, hsc)
            if not cand.hook:
                cand.hook = htext[:80]
    first = _text_between(tl.sentences, start, min(end, start + 8.0))
    if _QUESTION.search(first or ""):
        hook_score = max(hook_score, 0.5)
        if not cand.hook:
            cand.hook = first[:80]
    if hook_score > 0:
        evidence.append(f"hook:{hook_score:.2f}")

    # Boundary quality at edges
    boundary = 0.0
    for cut in tl.scene_cuts:
        if abs(cut - start) < 1.0 or abs(cut - end) < 1.0:
            boundary = max(boundary, 0.7)
            evidence.append(f"scene_cut@{cut:.1f}")
    for cut in tl.speaker_cuts:
        if abs(cut - start) < 1.0 or abs(cut - end) < 1.0:
            boundary = max(boundary, 0.55)
            evidence.append(f"speaker_cut@{cut:.1f}")
    for cut in tl.soft_cuts:
        if abs(cut - start) < 0.75 or abs(cut - end) < 0.75:
            boundary = max(boundary, 0.4)

    # Duration fitness
    dur = end - start
    rel = abs(dur - target) / max(target, 1.0)
    duration_fit = max(0.0, 1.0 - rel)

    # Signal density
    density = 0.0
    for s, e, sc in tl.intensity:
        if e >= start and s <= end:
            density = max(density, min(1.0, sc))
    if density > 0:
        evidence.append(f"intensity:{density:.2f}")

    silence_ratio = _silence_ratio(tl, start, end)
    silence_pen = silence_ratio  # higher = worse

    score = (
        W_SEED * seed_score
        + W_HOOK * hook_score
        + W_BOUNDARY * boundary
        + W_DURATION * duration_fit
        + W_DENSITY * density
        - W_SILENCE_PENALTY * silence_pen
    )
    score = min(1.0, max(0.0, score))

    reason_bits = [
        f"snapped to sentence boundaries",
        f"duration={dur:.1f}s (target={target:.0f}s)",
    ]
    if seed_score:
        reason_bits.append(f"seed={best_cat}:{seed_score:.2f}")
    if hook_score:
        reason_bits.append("hook present")
    if boundary:
        reason_bits.append("edge boundary support")
    reason_bits.append("not a fixed time chunk")

    return ClipCandidate(
        start=start,
        end=end,
        duration=dur,
        transcript=cand.transcript,
        category=best_cat or "story",
        score=score,
        hook=cand.hook or first[:80],
        reason="; ".join(reason_bits),
        title=cand.title or (cand.hook or cand.transcript)[:48],
        evidence=evidence,
        target_duration=float(cand.target_duration or target),
        source_signals=list(cand.source_signals or []),
    )


def _iou(a: ClipCandidate, b: ClipCandidate) -> float:
    inter = max(0.0, min(a.end, b.end) - max(a.start, b.start))
    if inter <= 0:
        return 0.0
    union = (a.end - a.start) + (b.end - b.start) - inter
    return inter / union if union > 0 else 0.0


def _greedy_select(
    ranked: list[ClipCandidate],
    *,
    max_n: int,
    max_iou: float,
) -> list[ClipCandidate]:
    kept: list[ClipCandidate] = []
    for cand in ranked:
        if any(_iou(cand, k) > max_iou for k in kept):
            continue
        kept.append(cand)
        if len(kept) >= max_n:
            break
    return kept
