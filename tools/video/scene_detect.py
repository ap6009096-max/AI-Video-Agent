"""Fused scene detection: reuse analysis signals + long-video merge/caps."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from config.settings import get_settings
from core.logging import get_logger
from schemas.scenes import ChangeKind, DetectedScene

logger = get_logger(__name__)


def detect_scenes(
    *,
    media_path: str | Path | None = None,
    analysis: dict[str, Any] | None = None,
    speech_transcript: dict[str, Any] | None = None,
    transcript: dict[str, Any] | None = None,
    min_duration: float | None = None,
    min_gap: float | None = None,
    max_scenes: int | None = None,
    speaker_gap: float | None = None,
) -> dict[str, Any]:
    """Fuse visual + speaker signals into DetectedScene list (no clips)."""
    settings = get_settings()
    min_dur = float(min_duration if min_duration is not None else settings.scene_min_duration)
    gap = float(min_gap if min_gap is not None else settings.scene_min_gap)
    max_n = int(max_scenes if max_scenes is not None else settings.scene_max_scenes)
    sp_gap = float(speaker_gap if speaker_gap is not None else settings.scene_speaker_gap)

    duration = _infer_duration(analysis, speech_transcript, transcript, media_path)
    candidates: list[dict[str, Any]] = []
    signals = {"visual": 0, "speaker": 0, "event": 0, "rescanned": 0}

    visual = _boundaries_from_analysis(analysis)
    if visual:
        candidates.extend(visual)
        signals["visual"] = len(visual)
    elif media_path and Path(media_path).is_file():
        rescanned = _rescan_media(Path(media_path))
        candidates.extend(rescanned)
        signals["rescanned"] = len(rescanned)
        signals["visual"] = len(rescanned)

    event_bounds = _boundaries_from_object_cues(analysis)
    if event_bounds:
        candidates.extend(event_bounds)
        signals["event"] = len(event_bounds)

    speaker_bounds = _boundaries_from_speech(
        speech_transcript, transcript, analysis, sp_gap
    )
    if speaker_bounds:
        candidates.extend(speaker_bounds)
        signals["speaker"] = len(speaker_bounds)

    scenes = build_detected_scenes(
        candidates,
        duration=duration,
        min_duration=min_dur,
        min_gap=gap,
        max_scenes=max_n,
    )
    logger.info(
        "Scene detection duration=%.2f scenes=%s signals=%s",
        duration,
        len(scenes),
        signals,
    )
    return {
        "scenes": scenes,
        "duration": duration,
        "source_signals": signals,
        "notes": "",
    }


def build_detected_scenes(
    candidates: list[dict[str, Any]],
    *,
    duration: float,
    min_duration: float = 1.5,
    min_gap: float = 0.4,
    max_scenes: int = 120,
) -> list[DetectedScene]:
    """Merge candidate boundaries into DetectedScene spans."""
    end = max(0.0, float(duration))
    # Aggregate by time with score + kinds
    buckets: dict[float, dict[str, Any]] = {}
    for c in candidates:
        t = float(c.get("time", 0.0))
        if t <= 0 or (end > 0 and t >= end):
            continue
        score = float(c.get("score", 0.0))
        kinds = list(c.get("kinds") or [])
        key = round(t, 3)
        # Snap into existing nearby bucket
        matched = None
        for bt in list(buckets.keys()):
            if abs(bt - key) <= min_gap:
                matched = bt
                break
        if matched is None:
            buckets[key] = {"time": key, "score": score, "kinds": set(kinds)}
        else:
            buckets[matched]["score"] = max(buckets[matched]["score"], score)
            buckets[matched]["kinds"].update(kinds)

    cuts = sorted(buckets.values(), key=lambda x: x["time"])
    if end > 0 and len(cuts) + 1 > max_scenes:
        keep_n = max(0, max_scenes - 1)
        cuts = sorted(cuts, key=lambda x: x["score"], reverse=True)[:keep_n]
        cuts = sorted(cuts, key=lambda x: x["time"])

    boundaries = [0.0] + [c["time"] for c in cuts]
    if end > 0:
        boundaries.append(end)
    else:
        boundaries.append(boundaries[-1] if len(boundaries) > 1 else 0.0)

    cleaned: list[float] = []
    for t in boundaries:
        if not cleaned or abs(t - cleaned[-1]) > min_gap * 0.5:
            cleaned.append(t)
        else:
            cleaned[-1] = t
    if len(cleaned) < 2:
        return [
            DetectedScene(
                id=0,
                start=0.0,
                end=end,
                duration=end,
                visual_change_score=0.0,
                description="Full timeline (no strong boundaries)",
                change_kinds=[],
            )
        ]

    score_at = {c["time"]: c for c in cuts}
    raw_spans: list[dict[str, Any]] = []
    for i in range(len(cleaned) - 1):
        start = cleaned[i]
        stop = cleaned[i + 1]
        meta = score_at.get(stop) or score_at.get(start) or {"score": 0.0, "kinds": set()}
        kinds = sorted(meta.get("kinds") or [])
        raw_spans.append(
            {
                "start": start,
                "end": stop,
                "score": float(meta.get("score") or 0.0),
                "kinds": kinds,
            }
        )

    merged = _merge_short_spans(raw_spans, min_duration)
    scenes: list[DetectedScene] = []
    for i, span in enumerate(merged):
        start = float(span["start"])
        stop = float(span["end"])
        dur = max(0.0, stop - start)
        kinds = [k for k in span.get("kinds") or [] if k in _VALID_KINDS]
        score = float(span.get("score") or 0.0)
        scenes.append(
            DetectedScene(
                id=i,
                start=start,
                end=stop,
                duration=dur,
                visual_change_score=score,
                description=describe_scene(kinds, score),
                change_kinds=kinds,  # type: ignore[arg-type]
            )
        )
    return scenes


_VALID_KINDS = frozenset(
    {"cut", "transition", "composition", "camera", "speaker", "event"}
)


def describe_scene(kinds: list[str], score: float) -> str:
    """Rule-based description from change kinds (no LLM)."""
    if not kinds:
        return "Stable visual segment"
    labels = {
        "cut": f"Hard cut (score={score:.2f})",
        "transition": f"Visual transition (score={score:.2f})",
        "composition": f"Composition change (score={score:.2f})",
        "camera": f"Camera movement (score={score:.2f})",
        "speaker": "Speaker pause then resume",
        "event": f"Significant visual event (score={score:.2f})",
    }
    parts = [labels[k] for k in kinds if k in labels]
    return "; ".join(parts) if parts else f"Scene change (score={score:.2f})"


def _merge_short_spans(
    spans: list[dict[str, Any]], min_duration: float
) -> list[dict[str, Any]]:
    if not spans:
        return []
    merged: list[dict[str, Any]] = [dict(spans[0])]
    for span in spans[1:]:
        cur = merged[-1]
        cur_dur = float(cur["end"]) - float(cur["start"])
        if cur_dur < min_duration:
            cur["end"] = span["end"]
            cur["score"] = max(float(cur["score"]), float(span["score"]))
            kinds = set(cur.get("kinds") or []) | set(span.get("kinds") or [])
            cur["kinds"] = sorted(kinds)
        else:
            merged.append(dict(span))
    # If last is too short, fold into previous
    if len(merged) >= 2:
        last = merged[-1]
        if float(last["end"]) - float(last["start"]) < min_duration:
            prev = merged[-2]
            prev["end"] = last["end"]
            prev["score"] = max(float(prev["score"]), float(last["score"]))
            prev["kinds"] = sorted(
                set(prev.get("kinds") or []) | set(last.get("kinds") or [])
            )
            merged.pop()
    return merged


def _infer_duration(
    analysis: dict[str, Any] | None,
    speech_transcript: dict[str, Any] | None,
    transcript: dict[str, Any] | None,
    media_path: str | Path | None,
) -> float:
    if analysis:
        props = analysis.get("properties") or {}
        try:
            d = float(props.get("duration_seconds") or 0.0)
            if d > 0:
                return d
        except (TypeError, ValueError):
            pass
        scenes = analysis.get("scenes") or []
        if scenes:
            try:
                return max(float(s.get("end", 0.0)) for s in scenes)
            except (TypeError, ValueError):
                pass
    ends: list[float] = []
    if speech_transcript:
        for seg in speech_transcript.get("segments") or []:
            try:
                ends.append(float(seg.get("end", 0.0)))
            except (TypeError, ValueError):
                continue
    if transcript:
        for sent in transcript.get("sentences") or []:
            try:
                ends.append(float(sent.get("end_seconds") or 0.0))
            except (TypeError, ValueError):
                continue
        for sec in transcript.get("sections") or []:
            try:
                ends.append(float(sec.get("end_seconds") or 0.0))
            except (TypeError, ValueError):
                continue
    if ends:
        return max(ends)
    return 0.0


def _boundaries_from_analysis(analysis: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not analysis:
        return []
    out: list[dict[str, Any]] = []
    for ch in analysis.get("visual_changes") or []:
        try:
            t = float(ch.get("time_seconds", 0.0))
            score = float(ch.get("score", 0.0))
        except (TypeError, ValueError):
            continue
        kind = str(ch.get("kind") or "cut")
        kinds: list[ChangeKind]
        if kind == "motion":
            kinds = ["transition"]
            if score >= 0.55:
                kinds.append("camera")
        else:
            kinds = ["cut"]
            if score >= 0.5:
                kinds.append("composition")
        out.append({"time": t, "score": score, "kinds": kinds})

    for sc in analysis.get("scenes") or []:
        try:
            t = float(sc.get("start", 0.0))
            score = float(sc.get("score", 0.0))
        except (TypeError, ValueError):
            continue
        if t > 0:
            out.append({"time": t, "score": score, "kinds": ["cut"]})

    for fr in analysis.get("sampled_frames") or []:
        try:
            motion = float(fr.get("motion_score", 0.0))
            t = float(fr.get("time_seconds", 0.0))
        except (TypeError, ValueError):
            continue
        if motion >= 0.45 and t > 0:
            out.append({"time": t, "score": motion, "kinds": ["transition", "camera"]})
    return out


def _boundaries_from_object_cues(analysis: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not analysis:
        return []
    out: list[dict[str, Any]] = []
    for cue in analysis.get("object_cues") or []:
        if cue.get("label") != "motion_hotspot":
            continue
        try:
            t = float(cue.get("time_seconds", 0.0))
        except (TypeError, ValueError):
            continue
        if t > 0:
            out.append({"time": t, "score": 0.5, "kinds": ["event"]})
    return out


def _boundaries_from_speech(
    speech_transcript: dict[str, Any] | None,
    transcript: dict[str, Any] | None,
    analysis: dict[str, Any] | None,
    speaker_gap: float,
) -> list[dict[str, Any]]:
    ranges: list[tuple[float, float]] = []
    if speech_transcript:
        for seg in speech_transcript.get("segments") or []:
            try:
                ranges.append((float(seg["start"]), float(seg["end"])))
            except (KeyError, TypeError, ValueError):
                continue
    elif analysis and analysis.get("speaker_presence"):
        for r in (analysis["speaker_presence"].get("speech_ranges") or []):
            try:
                ranges.append((float(r["start"]), float(r["end"])))
            except (KeyError, TypeError, ValueError):
                continue
    elif transcript:
        for sent in transcript.get("sentences") or []:
            try:
                s = float(sent.get("start_seconds"))
                e = float(sent.get("end_seconds"))
            except (TypeError, ValueError):
                continue
            ranges.append((s, e))

    ranges.sort(key=lambda x: x[0])
    out: list[dict[str, Any]] = []
    for i in range(len(ranges) - 1):
        gap = ranges[i + 1][0] - ranges[i][1]
        if gap >= speaker_gap:
            t = ranges[i][1] + gap / 2.0
            out.append({"time": t, "score": min(1.0, gap / 5.0), "kinds": ["speaker"]})

    if transcript:
        for sec in transcript.get("sections") or []:
            try:
                s = float(sec.get("start_seconds") or 0.0)
            except (TypeError, ValueError):
                continue
            if s > 0:
                out.append({"time": s, "score": 0.3, "kinds": ["speaker"]})

    if analysis:
        audio = analysis.get("audio") or {}
        for sil in audio.get("silence_ranges") or []:
            try:
                s = float(sil.get("start", 0.0))
                e = float(sil.get("end", s))
            except (TypeError, ValueError):
                continue
            if e - s >= speaker_gap:
                out.append(
                    {
                        "time": (s + e) / 2.0,
                        "score": min(1.0, (e - s) / 5.0),
                        "kinds": ["speaker"],
                    }
                )
    return out


def _rescan_media(media_path: Path) -> list[dict[str, Any]]:
    """Optional OpenCV rescan when analysis lacks visual signals."""
    try:
        from tools.video.scenes import analyze_scenes
    except Exception as exc:  # noqa: BLE001
        logger.warning("Scene rescan unavailable: %s", exc)
        return []

    try:
        result = analyze_scenes(media_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Scene rescan failed: %s", exc)
        return []

    faux = {
        "visual_changes": [
            c.model_dump(mode="json") if hasattr(c, "model_dump") else c
            for c in (result.get("visual_changes") or [])
        ],
        "scenes": [
            s.model_dump(mode="json") if hasattr(s, "model_dump") else s
            for s in (result.get("scenes") or [])
        ],
        "sampled_frames": [
            f.model_dump(mode="json") if hasattr(f, "model_dump") else f
            for f in (result.get("sampled_frames") or [])
        ],
        "object_cues": [
            o.model_dump(mode="json") if hasattr(o, "model_dump") else o
            for o in (result.get("object_cues") or [])
        ],
    }
    return _boundaries_from_analysis(faux) + _boundaries_from_object_cues(faux)
