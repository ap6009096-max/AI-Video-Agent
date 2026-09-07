"""Package podcast video/audio into platform-oriented short clips."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config.settings import get_settings
from core.logging import get_logger
from schemas.job import ALLOWED_AUDIO_UPLOAD_EXTENSIONS
from schemas.podcast import PodcastClip, PodcastClipKind, PodcastPlatform

logger = get_logger(__name__)

KIND_PLATFORMS: dict[str, list[PodcastPlatform]] = {
    "quote": ["quotes", "shorts"],
    "funny": ["reels", "tiktok", "shorts"],
    "viral": ["reels", "tiktok", "shorts"],
    "lesson": ["shorts", "highlights"],
    "highlight": ["highlights", "clips"],
    "clip": ["clips", "shorts"],
}


@dataclass
class _Seed:
    start: float
    end: float
    score: float
    kind: PodcastClipKind
    transcript: str = ""
    title: str = ""
    hook: str = ""
    reason: str = ""
    source_category: str = ""
    evidence: list[str] | None = None


def is_podcast_video_type(video_type: str | None) -> bool:
    key = (video_type or "").strip().lower()
    return key in {"podcast", "interview"} or "podcast" in key or "interview" in key


def detect_source_media(
    *,
    upload_path: str | None = None,
    analysis: dict[str, Any] | None = None,
    source_metadata: dict[str, Any] | None = None,
) -> str:
    path = (upload_path or "").strip()
    if path:
        ext = Path(path).suffix.lower()
        if ext in ALLOWED_AUDIO_UPLOAD_EXTENSIONS:
            return "audio"
        if ext in {".mp4", ".mov", ".avi", ".mkv", ".webm"}:
            return "video"
    props = (analysis or {}).get("properties") or {}
    try:
        frames = int(props.get("frame_count") or props.get("total_frames") or 0)
        width = int(props.get("width") or 0)
        height = int(props.get("height") or 0)
        if frames <= 1 and width <= 0 and height <= 0:
            dur = float(props.get("duration_seconds") or 0.0)
            if dur > 0:
                return "audio"
    except (TypeError, ValueError):
        pass
    if source_metadata and source_metadata.get("media_kind") == "audio":
        return "audio"
    if analysis:
        return "video"
    return "unknown"


def package_podcast_clips(
    *,
    transcript: dict[str, Any] | None = None,
    speech_transcript: dict[str, Any] | None = None,
    moments: dict[str, Any] | None = None,
    funny_moments: dict[str, Any] | None = None,
    viral_moments: dict[str, Any] | None = None,
    clips: dict[str, Any] | None = None,
    analysis: dict[str, Any] | None = None,
    upload_path: str | None = None,
    source_metadata: dict[str, Any] | None = None,
    target_duration: float | None = None,
    max_clips: int | None = None,
    min_score: float | None = None,
    max_overlap: float = 0.35,
) -> list[PodcastClip]:
    """Map upstream detections into ranked podcast platform packages."""
    settings = get_settings()
    target = float(
        target_duration
        if target_duration is not None
        else settings.podcast_target_duration
    )
    max_n = int(max_clips if max_clips is not None else settings.podcast_max_clips)
    min_s = float(min_score if min_score is not None else settings.podcast_min_score)

    seeds = _collect_seeds(
        transcript=transcript,
        speech_transcript=speech_transcript,
        moments=moments,
        funny_moments=funny_moments,
        viral_moments=viral_moments,
        clips=clips,
    )
    if not seeds:
        logger.info("Podcast package: no seeds")
        return []

    packaged: list[PodcastClip] = []
    for seed in seeds:
        clip = _seed_to_clip(seed, target=target)
        if clip.score < min_s:
            continue
        packaged.append(clip)

    packaged.sort(key=lambda c: c.score, reverse=True)
    selected = _greedy_select(packaged, max_n=max_n, max_iou=max_overlap)
    for i, c in enumerate(selected):
        c.id = i
        if c.duration <= 0:
            c.duration = max(0.0, c.end - c.start)

    logger.info("Podcast package selected %s clips from %s seeds", len(selected), len(seeds))
    return selected


def _collect_seeds(
    *,
    transcript: dict[str, Any] | None,
    speech_transcript: dict[str, Any] | None,
    moments: dict[str, Any] | None,
    funny_moments: dict[str, Any] | None,
    viral_moments: dict[str, Any] | None,
    clips: dict[str, Any] | None,
) -> list[_Seed]:
    seeds: list[_Seed] = []
    sent_times = _sentence_times(transcript, speech_transcript)

    for item in (moments or {}).get("moments") or []:
        kind = _kind_from_moment_category(str(item.get("category") or ""))
        if not kind:
            continue
        seed = _from_span_dict(
            item,
            kind=kind,
            score_key="score",
            title_key="title",
            reason_key="reason",
            source=str(item.get("category") or ""),
        )
        if seed:
            seeds.append(seed)

    for item in (funny_moments or {}).get("moments") or []:
        seed = _from_span_dict(
            item,
            kind="funny",
            score_key="humor_score",
            title_key="suggested_title",
            reason_key="explanation",
            source="funny",
        )
        if seed:
            seeds.append(seed)

    for item in (viral_moments or {}).get("moments") or []:
        seed = _from_span_dict(
            item,
            kind="viral",
            score_key="final_score",
            title_key="suggested_title",
            reason_key="explanation",
            source="viral",
        )
        if seed:
            seeds.append(seed)

    # Transcript hooks / important → quotes & lessons
    for hook in (transcript or {}).get("hooks") or []:
        span = _resolve_sentence_span(hook, sent_times)
        if not span:
            continue
        text = str(hook.get("text") or span[2] or "").strip()
        seeds.append(
            _Seed(
                start=span[0],
                end=span[1],
                score=float(hook.get("score") or 0.7),
                kind="quote",
                transcript=text,
                title=text[:48],
                hook=text[:80],
                reason=str(hook.get("reason") or "hook quote"),
                source_category="hook",
                evidence=["transcript:hook"],
            )
        )

    for imp in (transcript or {}).get("important_statements") or []:
        span = _resolve_sentence_span(imp, sent_times)
        if not span:
            continue
        text = str(imp.get("text") or span[2] or "").strip()
        seeds.append(
            _Seed(
                start=span[0],
                end=span[1],
                score=0.65,
                kind="lesson",
                transcript=text,
                title=text[:48],
                hook=text[:80],
                reason=str(imp.get("reason") or "key lesson"),
                source_category="important",
                evidence=["transcript:important"],
            )
        )

    # Smart clips → highlight / clip
    for item in (clips or {}).get("clips") or []:
        try:
            start = float(item.get("start", 0.0))
            end = float(item.get("end", start))
            score = float(item.get("score", 0.5))
        except (TypeError, ValueError):
            continue
        if end <= start:
            continue
        cat = str(item.get("category") or "").lower()
        kind: PodcastClipKind = "highlight" if score >= 0.55 else "clip"
        if cat in {"funny", "viral", "quote"}:
            kind = cat  # type: ignore[assignment]
        elif cat in {"important", "educational", "expert"}:
            kind = "lesson"
        seeds.append(
            _Seed(
                start=start,
                end=end,
                score=score,
                kind=kind,
                transcript=str(item.get("transcript") or ""),
                title=str(item.get("title") or item.get("hook") or "")[:48],
                hook=str(item.get("hook") or item.get("title") or "")[:80],
                reason=str(item.get("reason") or "smart clip package"),
                source_category=cat or "smart_clip",
                evidence=["smart_clip"],
            )
        )

    return seeds


def _kind_from_moment_category(category: str) -> PodcastClipKind | None:
    c = category.lower().strip()
    mapping: dict[str, PodcastClipKind] = {
        "quote": "quote",
        "funny": "funny",
        "viral": "viral",
        "important": "lesson",
        "educational": "lesson",
        "expert": "lesson",
        "inspirational": "lesson",
    }
    return mapping.get(c)


def _from_span_dict(
    item: dict[str, Any],
    *,
    kind: PodcastClipKind,
    score_key: str,
    title_key: str,
    reason_key: str,
    source: str,
) -> _Seed | None:
    try:
        start = float(item.get("start", 0.0))
        end = float(item.get("end", start))
        score = float(item.get(score_key, item.get("score", 0.5)))
    except (TypeError, ValueError):
        return None
    if end <= start:
        return None
    text = str(item.get("transcript") or "")
    title = str(item.get(title_key) or item.get("title") or text)[:48]
    hook = str(item.get("hook") or title or text)[:80]
    return _Seed(
        start=start,
        end=end,
        score=score,
        kind=kind,
        transcript=text,
        title=title,
        hook=hook,
        reason=str(item.get(reason_key) or item.get("reason") or f"{kind} seed"),
        source_category=source,
        evidence=[f"seed:{source}"],
    )


def _sentence_times(
    transcript: dict[str, Any] | None,
    speech_transcript: dict[str, Any] | None,
) -> dict[str, tuple[float, float, str]]:
    out: dict[str, tuple[float, float, str]] = {}
    if transcript:
        for sent in transcript.get("sentences") or []:
            sid = str(sent.get("id") or "")
            try:
                start = sent.get("start_seconds")
                end = sent.get("end_seconds")
                if start is None or end is None:
                    continue
                start_f = float(start)
                end_f = float(end)
            except (TypeError, ValueError):
                continue
            text = str(sent.get("text") or "")
            if sid and end_f > start_f:
                out[sid] = (start_f, end_f, text)
            idx = sent.get("index")
            if isinstance(idx, int) and end_f > start_f:
                out[f"idx:{idx}"] = (start_f, end_f, text)
    if not out and speech_transcript:
        for i, seg in enumerate(speech_transcript.get("segments") or []):
            try:
                start_f = float(seg.get("start", 0.0))
                end_f = float(seg.get("end", start_f))
            except (TypeError, ValueError):
                continue
            text = str(seg.get("text") or "")
            if end_f > start_f:
                out[f"seg:{i}"] = (start_f, end_f, text)
                out[f"idx:{i}"] = (start_f, end_f, text)
    return out


def _resolve_sentence_span(
    item: dict[str, Any],
    sent_times: dict[str, tuple[float, float, str]],
) -> tuple[float, float, str] | None:
    sid = str(item.get("sentence_id") or "")
    if sid and sid in sent_times:
        return sent_times[sid]
    idx = item.get("sentence_index")
    if isinstance(idx, int):
        key = f"idx:{idx}"
        if key in sent_times:
            return sent_times[key]
    return None


def _seed_to_clip(seed: _Seed, *, target: float) -> PodcastClip:
    start, end = seed.start, seed.end
    duration = max(0.0, end - start)
    # Soft pad toward target without inventing fixed tiles
    if duration < target * 0.5:
        pad = (target - duration) / 2.0
        start = max(0.0, start - pad * 0.35)
        end = end + pad * 0.65
        duration = end - start

    rel = abs(duration - target) / max(target, 1.0)
    duration_fit = max(0.0, 1.0 - rel)
    hook_boost = 0.1 if seed.hook else 0.0
    score = min(1.0, max(seed.score, 0.4 * seed.score + 0.4 * duration_fit + hook_boost))

    platforms = list(KIND_PLATFORMS.get(seed.kind, ["clips", "shorts"]))
    reason = (
        f"{seed.reason}; packaged as {seed.kind} for "
        f"{', '.join(platforms)}; target~{target:.0f}s"
    )
    return PodcastClip(
        start=start,
        end=end,
        duration=duration,
        kind=seed.kind,
        platforms=platforms,
        transcript=seed.transcript,
        title=seed.title or seed.hook[:48] or f"{seed.kind} clip",
        hook=seed.hook or seed.title,
        reason=reason,
        score=score,
        evidence=list(seed.evidence or []),
        source_category=seed.source_category,
    )


def _iou(a: PodcastClip, b: PodcastClip) -> float:
    inter = max(0.0, min(a.end, b.end) - max(a.start, b.start))
    if inter <= 0:
        return 0.0
    union = (a.end - a.start) + (b.end - b.start) - inter
    return inter / union if union > 0 else 0.0


def _greedy_select(
    ranked: list[PodcastClip],
    *,
    max_n: int,
    max_iou: float,
) -> list[PodcastClip]:
    kept: list[PodcastClip] = []
    for cand in ranked:
        if any(_iou(cand, k) > max_iou for k in kept):
            continue
        kept.append(cand)
        if len(kept) >= max_n:
            break
    return kept
