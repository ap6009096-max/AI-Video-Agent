"""Lightweight object cues on scene-change / clip keyframes only."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


def _sample_times_from_scenes(
    scenes: dict[str, Any] | None, *, max_keyframes: int = 24
) -> list[float]:
    times: list[float] = []
    if not isinstance(scenes, dict):
        return times
    items = scenes.get("scenes") or scenes.get("cuts") or []
    if not isinstance(items, list):
        return times
    for sc in items:
        if not isinstance(sc, dict):
            continue
        for key in ("start", "start_seconds", "time", "time_seconds"):
            if key in sc:
                try:
                    times.append(float(sc[key]))
                except (TypeError, ValueError):
                    pass
                break
    # Prefer unique, capped
    out: list[float] = []
    seen: set[float] = set()
    for t in times:
        rt = round(t, 2)
        if rt in seen:
            continue
        seen.add(rt)
        out.append(float(t))
        if len(out) >= max_keyframes:
            break
    return out


def _sample_times_from_clips(
    clips: dict[str, Any] | None, *, max_keyframes: int = 12
) -> list[float]:
    times: list[float] = []
    if not isinstance(clips, dict):
        return times
    items = clips.get("clips") or clips.get("items") or []
    if not isinstance(items, list):
        return times
    for clip in items:
        if not isinstance(clip, dict):
            continue
        try:
            start = float(clip.get("start") or clip.get("start_seconds") or 0)
            end = float(clip.get("end") or clip.get("end_seconds") or start)
        except (TypeError, ValueError):
            continue
        mid = (start + end) / 2.0
        times.append(mid)
        if len(times) >= max_keyframes:
            break
    return times


def detect_objects_at_keyframes(
    media_path: str | Path | None,
    *,
    scenes: dict[str, Any] | None = None,
    clips: dict[str, Any] | None = None,
    enabled: bool = True,
    max_keyframes: int = 24,
) -> dict[str, Any]:
    """Soft object-detection scaffold on keyframes (no heavy model required).

    Uses OpenCV frame sampling + simple motion/edge heuristics when available.
    Soft-skips when disabled or media missing.
    """
    if not enabled:
        return {
            "skipped": True,
            "reason": "object_detection disabled",
            "objects": [],
            "keyframes": [],
        }

    times = _sample_times_from_scenes(scenes, max_keyframes=max_keyframes)
    if not times:
        times = _sample_times_from_clips(clips, max_keyframes=max_keyframes // 2)
    if not times:
        return {
            "skipped": True,
            "reason": "no scene/clip keyframes",
            "objects": [],
            "keyframes": [],
        }

    path = Path(media_path) if media_path else None
    if path is None or not path.is_file():
        return {
            "skipped": True,
            "reason": "media missing",
            "objects": [],
            "keyframes": [{"time_seconds": t} for t in times],
        }

    objects: list[dict[str, Any]] = []
    keyframes: list[dict[str, Any]] = []

    try:
        import cv2  # type: ignore
    except ImportError:
        return {
            "skipped": True,
            "reason": "opencv unavailable",
            "objects": [],
            "keyframes": [{"time_seconds": t} for t in times],
        }

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return {
            "skipped": True,
            "reason": "cannot open media",
            "objects": [],
            "keyframes": [{"time_seconds": t} for t in times],
        }

    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0) or 30.0
        for t in times:
            idx = int(max(0.0, t) * fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
            if not ok or frame is None:
                keyframes.append({"time_seconds": t, "ok": False})
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 80, 160)
            density = float(edges.mean()) / 255.0
            label = "high_detail" if density > 0.12 else "low_detail"
            h, w = gray.shape[:2]
            obj = {
                "time_seconds": round(t, 3),
                "label": label,
                "detail": f"edge_density={density:.3f}",
                "x": 0.5,
                "y": 0.5,
                "score": round(min(1.0, density * 4), 3),
                "frame_w": int(w),
                "frame_h": int(h),
            }
            objects.append(obj)
            keyframes.append({"time_seconds": t, "ok": True, "label": label})
    finally:
        cap.release()

    return {
        "skipped": False,
        "reason": "",
        "objects": objects,
        "keyframes": keyframes,
        "notes": "Keyframe object cues (edge heuristic). Soft-skip when no scenes/clips.",
    }


def write_objects_json(project_dir: str | Path, payload: dict[str, Any]) -> str:
    root = Path(project_dir)
    path = root / "analysis" / "objects.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("Wrote objects.json → %s skipped=%s", path, payload.get("skipped"))
    return str(path)
