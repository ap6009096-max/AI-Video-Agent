"""Selective FFmpeg stitch: replace one scene window, preserve the rest."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from core.logging import get_logger
from core.versioning import create_version, ensure_current_dir
from schemas.render import RenderOp
from schemas.transform_intent import TransformIntent
from tools.ffmpeg.audio_ops import sync_voice_to_video
from tools.ffmpeg.edit import concat_segments, cut_segment
from tools.ffmpeg.probe import probe_media

logger = get_logger(__name__)


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def resolve_scene_window(
    scenes: dict[str, Any] | None,
    target_scene: int | str,
    *,
    fallback_start: float = 0.0,
    fallback_end: float = 0.0,
) -> tuple[float, float, int]:
    """Return (start, end, index0) for the target scene."""
    items: list[dict[str, Any]] = []
    if isinstance(scenes, dict):
        raw = scenes.get("scenes") or scenes.get("cuts") or []
        if isinstance(raw, list):
            for row in raw:
                if isinstance(row, dict):
                    items.append(row)

    idx = 0
    if isinstance(target_scene, int):
        idx = max(0, target_scene - 1)
    else:
        text = str(target_scene).strip().lower()
        if text.isdigit():
            idx = max(0, int(text) - 1)
        else:
            for i, row in enumerate(items):
                sid = str(row.get("scene_id") or row.get("id") or "").strip().lower()
                if sid and (sid == text or text in sid):
                    idx = i
                    break

    if 0 <= idx < len(items):
        row = items[idx]
        start = _as_float(
            row.get("start")
            or row.get("start_seconds")
            or row.get("start_time")
            or fallback_start
        )
        end = _as_float(
            row.get("end")
            or row.get("end_seconds")
            or row.get("end_time")
            or fallback_end
        )
        if end > start:
            return start, end, idx

    if fallback_end > fallback_start:
        return fallback_start, fallback_end, idx
    return 0.0, 0.0, idx


def apply_selective_transform(
    media: Path,
    *,
    intent: TransformIntent,
    scenes: dict[str, Any] | None,
    renders: Path,
    voice_audio: Path | None = None,
    project_dir: Path | None = None,
) -> tuple[Path | None, list[RenderOp], dict[str, Any]]:
    """Cut around the target window, optionally mux VO, concat back to a new MP4.

    Returns (output_or_None, ops, metrics).
    """
    ops: list[RenderOp] = []
    metrics: dict[str, Any] = {
        "applied": False,
        "start": 0.0,
        "end": 0.0,
        "scenes_changed": intent.scenes_changed,
        "scenes_total": intent.scenes_total,
        "scenes_preserved": intent.scenes_preserved,
    }
    if not media.is_file():
        return None, ops, metrics

    start = float(intent.start_seconds or 0.0)
    end = float(intent.end_seconds or 0.0)
    if end <= start:
        start, end, _idx = resolve_scene_window(
            scenes,
            intent.target_scene,
            fallback_start=start,
            fallback_end=end,
        )
    if end <= start:
        # Default: first 10s window when scenes unknown
        info = probe_media(media) or {}
        dur = float(info.get("duration") or 0.0)
        start = 0.0
        end = min(10.0, dur) if dur > 0 else 5.0

    # Shorten: trim last 25% of the window when requested
    scope = {str(s).lower() for s in intent.regeneration_scope}
    changes_l = " ".join(intent.requested_changes).lower()
    if "trim" in scope or "shorten" in changes_l:
        span = end - start
        end = start + max(0.5, span * 0.75)
        ops.append(RenderOp(name="trim_scene", detail=f"{start:.2f}-{end:.2f}"))

    metrics["start"] = start
    metrics["end"] = end

    info = probe_media(media) or {}
    total_dur = float(info.get("duration") or 0.0)
    if total_dur <= 0:
        total_dur = end + 1.0

    work = renders / "_transform"
    work.mkdir(parents=True, exist_ok=True)
    segments: list[Path] = []

    if start > 0.05:
        before = work / "before.mp4"
        cut = cut_segment(media, before, start=0.0, end=start)
        if cut is not None:
            segments.append(cut)
            ops.append(RenderOp(name="preserve_before", detail=f"0.00-{start:.2f}"))

    mid = work / "changed.mp4"
    changed = cut_segment(media, mid, start=start, end=end)
    if changed is None:
        return None, ops, metrics
    ops.append(RenderOp(name="extract_changed", detail=f"{start:.2f}-{end:.2f}"))

    if voice_audio is not None and voice_audio.is_file() and (
        "voice" in scope or "dialogue" in scope
    ):
        voiced = work / "changed_vo.mp4"
        try:
            sync_voice_to_video(changed, voice_audio, voiced)
            if voiced.is_file() and voiced.stat().st_size > 0:
                changed = voiced
                ops.append(RenderOp(name="mux_voice", detail=str(voice_audio.name)))
        except Exception as exc:  # noqa: BLE001
            logger.info("Selective voice mux soft-skipped: %s", exc)

    segments.append(changed)

    if end < total_dur - 0.05:
        after = work / "after.mp4"
        cut = cut_segment(media, after, start=end, end=total_dur)
        if cut is not None:
            segments.append(cut)
            ops.append(RenderOp(name="preserve_after", detail=f"{end:.2f}-{total_dur:.2f}"))

    stitched = work / "stitched.mp4"
    joined = concat_segments(segments, stitched)
    if joined is None or not joined.is_file():
        return None, ops, metrics

    out = renders / "final.mp4"
    try:
        if project_dir is not None:
            create_version(project_dir)
        shutil.copy2(joined, out)
        if project_dir is not None:
            current = ensure_current_dir(project_dir)
            shutil.copy2(out, current / "final.mp4")
    except OSError as exc:
        logger.warning("Failed to write selective final: %s", exc)
        return None, ops, metrics

    ops.append(RenderOp(name="selective_stitch", detail=str(out)))
    metrics["applied"] = True
    metrics["output_path"] = str(out)
    return out, ops, metrics
