"""Speaker turn / conversational structure heuristics (not diarization)."""

from __future__ import annotations

from typing import Any

from config.settings import get_settings
from core.logging import get_logger
from schemas.audio_speakers import (
    ConversationalStructure,
    ScoredSpan,
    SpeakerTurn,
)

logger = get_logger(__name__)


def analyze_speakers(
    *,
    speech_transcript: dict[str, Any] | None = None,
    transcript: dict[str, Any] | None = None,
    audio_analysis: dict[str, Any] | None = None,
    scenes: dict[str, Any] | None = None,
    analysis: dict[str, Any] | None = None,
    turn_gap: float | None = None,
) -> dict[str, Any]:
    """Build turn candidates and conversational scores from transcript gaps."""
    settings = get_settings()
    gap_thr = float(turn_gap if turn_gap is not None else settings.speaker_turn_gap)

    units = _units(speech_transcript, transcript, analysis)
    turns = _build_turns(units, gap_thr)
    changes = _speaker_changes(turns, audio_analysis, gap_thr)
    changes.extend(_changes_from_scenes(scenes))
    changes = _dedupe_changes(changes)

    structure = _conversational_structure(turns, changes)
    duration = 0.0
    if turns:
        duration = max(t.end for t in turns)
    change_rate = (len(changes) / (duration / 60.0)) if duration > 0 else 0.0
    summary = {
        "speaker_change_rate": min(1.0, change_rate / 8.0),
        "turn_count": float(len(turns)),
        "turn_taking": structure.turn_taking,
        "monologue_ratio": structure.monologue_ratio,
        "backchannel_density": structure.backchannel_density,
        "overlap_proxy": structure.overlap_proxy,
    }

    logger.info(
        "Speaker analysis turns=%s changes=%s turn_taking=%.2f",
        len(turns),
        len(changes),
        structure.turn_taking,
    )
    return {
        "turns": turns,
        "speaker_change_candidates": changes,
        "conversational_structure": structure,
        "summary_scores": summary,
        "notes": (
            "Speaker-independent turn heuristics — not true diarization or voice IDs."
        ),
    }


def _units(
    speech_transcript: dict[str, Any] | None,
    transcript: dict[str, Any] | None,
    analysis: dict[str, Any] | None,
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
    elif analysis and analysis.get("speaker_presence"):
        for r in (analysis["speaker_presence"].get("speech_ranges") or []):
            try:
                start = float(r.get("start", 0.0))
                end = float(r.get("end", start))
            except (TypeError, ValueError):
                continue
            if end > start:
                units.append({"start": start, "end": end, "text": ""})
    units.sort(key=lambda u: u["start"])
    return units


def _build_turns(units: list[dict[str, Any]], gap_thr: float) -> list[SpeakerTurn]:
    if not units:
        return []
    groups: list[list[dict[str, Any]]] = [[units[0]]]
    for u in units[1:]:
        prev = groups[-1][-1]
        if float(u["start"]) - float(prev["end"]) >= gap_thr:
            groups.append([u])
        else:
            groups[-1].append(u)

    turns: list[SpeakerTurn] = []
    for i, group in enumerate(groups):
        start = float(group[0]["start"])
        end = float(group[-1]["end"])
        text = " ".join(g["text"] for g in group if g["text"]).strip()
        change = 0.0
        if i > 0:
            prev_end = float(groups[i - 1][-1]["end"])
            change = min(1.0, (start - prev_end) / 3.0)
        turns.append(
            SpeakerTurn(
                id=i,
                start=start,
                end=end,
                text_excerpt=text[:160],
                change_score=change,
            )
        )
    return turns


def _speaker_changes(
    turns: list[SpeakerTurn],
    audio_analysis: dict[str, Any] | None,
    gap_thr: float,
) -> list[ScoredSpan]:
    silence = []
    if audio_analysis:
        silence = audio_analysis.get("silence_spans") or audio_analysis.get("pause_spans") or []

    out: list[ScoredSpan] = []
    for i in range(1, len(turns)):
        prev, cur = turns[i - 1], turns[i]
        gap = cur.start - prev.end
        if gap < gap_thr * 0.5:
            continue
        score = min(1.0, gap / 3.0)
        # Boost if silence/pause overlaps the gap
        for s in silence:
            try:
                ss = float(s.get("start", 0.0) if isinstance(s, dict) else s.start)
                se = float(s.get("end", ss) if isinstance(s, dict) else s.end)
            except (TypeError, ValueError, AttributeError):
                continue
            if se >= prev.end and ss <= cur.start:
                score = min(1.0, score + 0.15)
                break
        out.append(
            ScoredSpan(
                start=prev.end,
                end=cur.start,
                score=max(score, cur.change_score),
                label="speaker_change",
                evidence_tags=["clip_boundary", "reaction"],
                detail=f"turn_gap={gap:.2f}s",
            )
        )
    return out


def _changes_from_scenes(scenes: dict[str, Any] | None) -> list[ScoredSpan]:
    if not scenes:
        return []
    out: list[ScoredSpan] = []
    for sc in scenes.get("scenes") or []:
        kinds = sc.get("change_kinds") or []
        if "speaker" not in kinds:
            continue
        try:
            start = float(sc.get("start", 0.0))
            # Boundary at scene start
            t = start
            score = float(sc.get("visual_change_score") or 0.4)
        except (TypeError, ValueError):
            continue
        if t <= 0:
            continue
        out.append(
            ScoredSpan(
                start=max(0.0, t - 0.1),
                end=t + 0.1,
                score=min(1.0, max(0.3, score)),
                label="speaker_change",
                evidence_tags=["clip_boundary"],
                detail="from_scene_speaker_kind",
            )
        )
    return out


def _dedupe_changes(changes: list[ScoredSpan]) -> list[ScoredSpan]:
    if not changes:
        return []
    changes = sorted(changes, key=lambda c: c.start)
    merged: list[ScoredSpan] = [changes[0]]
    for c in changes[1:]:
        prev = merged[-1]
        if abs(c.start - prev.start) < 0.4:
            if c.score > prev.score:
                merged[-1] = c
        else:
            merged.append(c)
    return merged


def _conversational_structure(
    turns: list[SpeakerTurn],
    changes: list[ScoredSpan],
) -> ConversationalStructure:
    if not turns:
        return ConversationalStructure()
    durations = [max(0.05, t.end - t.start) for t in turns]
    total = sum(durations)
    mean = total / len(durations)
    variance = sum((d - mean) ** 2 for d in durations) / len(durations)
    # High turn count with moderate gaps → turn_taking
    turn_taking = min(1.0, (len(changes) / max(1, len(turns) - 1)) if len(turns) > 1 else 0.0)
    # Long single turn share
    monologue = max(durations) / total if total > 0 else 0.0
    # Short turns as backchannels
    backchannels = sum(1 for d in durations if d <= 1.2)
    backchannel_density = backchannels / len(turns)
    # Overlap proxy: very small gaps between turns (near-zero) relative to count
    tiny_gaps = 0
    for i in range(1, len(turns)):
        g = turns[i].start - turns[i - 1].end
        if 0 <= g < 0.15:
            tiny_gaps += 1
    overlap_proxy = tiny_gaps / max(1, len(turns) - 1) if len(turns) > 1 else 0.0
    # Dampen turn_taking when variance is extreme (one monologue + noise)
    if monologue > 0.75:
        turn_taking *= 0.5
    return ConversationalStructure(
        turn_taking=float(turn_taking),
        overlap_proxy=float(min(1.0, overlap_proxy)),
        monologue_ratio=float(min(1.0, monologue)),
        backchannel_density=float(min(1.0, backchannel_density)),
    )
