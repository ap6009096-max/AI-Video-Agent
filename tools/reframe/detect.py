"""OpenCV focus detection for smart reframing (faces, speakers, motion)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.logging import get_logger
from schemas.reframe import FocusRoi
from tools.reframe.catalog import detection_settings
from tools.video.probe import compute_frame_step

logger = get_logger(__name__)


def _load_face_cascade():  # type: ignore[no-untyped-def]
    import cv2  # type: ignore

    path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
    cascade = cv2.CascadeClassifier(str(path))
    if cascade.empty():
        logger.warning("Haar face cascade failed to load from %s", path)
        return None
    return cascade


def _speaker_active(t: float, turns: list[dict[str, Any]]) -> bool:
    for turn in turns:
        try:
            start = float(turn.get("start", -1))
            end = float(turn.get("end", -1))
        except (TypeError, ValueError):
            continue
        if start <= t <= end:
            return True
    return False


def _motion_points(
    analysis: dict[str, Any] | None, t: float, *, window: float = 0.75
) -> list[tuple[float, float, float]]:
    """Return (cx_norm, cy_norm, score) from object_cues near time t."""
    if not isinstance(analysis, dict):
        return []
    cues = analysis.get("object_cues") or []
    if not isinstance(cues, list):
        return []
    points: list[tuple[float, float, float]] = []
    for cue in cues:
        if not isinstance(cue, dict):
            continue
        try:
            ct = float(cue.get("time_seconds", -999))
        except (TypeError, ValueError):
            continue
        if abs(ct - t) > window:
            continue
        label = str(cue.get("label") or "")
        detail = str(cue.get("detail") or "")
        # Prefer explicit coords in detail if present: "x=0.4,y=0.3"
        cx, cy = 0.5, 0.45
        if "x=" in detail and "y=" in detail:
            try:
                parts = dict(
                    p.split("=") for p in detail.replace(" ", "").split(",") if "=" in p
                )
                cx = float(parts.get("x", 0.5))
                cy = float(parts.get("y", 0.45))
            except (TypeError, ValueError):
                pass
        score = 0.6 if label == "motion_hotspot" else 0.4
        points.append((cx, cy, score))
    return points


def _frame_motion_band(gray_small) -> tuple[float, float, float] | None:  # type: ignore[no-untyped-def]
    """Content-aware horizontal focus from column variance (no face)."""
    import numpy as np  # type: ignore

    # gray_small: HxW uint8
    col_var = np.var(gray_small.astype("float32"), axis=0)
    if col_var.size == 0 or float(col_var.max()) < 1.0:
        return None
    idx = int(np.argmax(col_var))
    cx = (idx + 0.5) / max(1, gray_small.shape[1])
    cy = 0.42  # slight upper bias for talking-head framing
    score = float(col_var[idx] / (col_var.mean() + 1e-6))
    score = min(1.0, score / 10.0)
    return (cx, cy, max(0.15, score))


def score_face_rois(
    faces: list[tuple[int, int, int, int]],
    *,
    frame_w: int,
    frame_h: int,
    time_seconds: float,
    speaker_active: bool,
    motion_pts: list[tuple[float, float, float]],
    speaker_boost: float,
    motion_boost: float,
) -> list[FocusRoi]:
    """Score detected face boxes; prefer larger + speaker + near motion."""
    rois: list[FocusRoi] = []
    for x, y, w, h in faces:
        area = float(w * h) / max(1.0, float(frame_w * frame_h))
        cx = (x + w / 2) / max(1, frame_w)
        cy = (y + h / 2) / max(1, frame_h)
        score = area * 4.0
        kind = "face"
        if speaker_active:
            score *= speaker_boost
            kind = "speaker_face"
        for mx, my, ms in motion_pts:
            dist = ((cx - mx) ** 2 + (cy - my) ** 2) ** 0.5
            if dist < 0.25:
                score *= motion_boost * (1.0 + ms)
        rois.append(
            FocusRoi(
                kind=kind,
                x=float(x),
                y=float(y),
                w=float(w),
                h=float(h),
                score=float(score),
                time_seconds=time_seconds,
            )
        )
    rois.sort(key=lambda r: r.score, reverse=True)
    return rois


def detect_focus_samples(
    media_path: str | Path,
    *,
    analysis: dict[str, Any] | None = None,
    speakers: dict[str, Any] | None = None,
    start: float = 0.0,
    end: float | None = None,
    enable_face: bool = True,
) -> list[FocusRoi]:
    """Sample frames and return best focus ROI per sample time."""
    try:
        import cv2  # type: ignore
    except ImportError:
        logger.warning("OpenCV unavailable — no focus samples")
        return []

    path = Path(media_path)
    if not path.is_file():
        return []

    settings = detection_settings()
    sample_fps = min(2.0, float(settings.get("sample_fps", 2.0)))
    max_frames = int(settings.get("max_frames", 120))
    face_min = int(settings.get("face_min_size", 40))
    speaker_boost = float(settings.get("speaker_boost", 1.75))
    motion_boost = float(settings.get("motion_boost", 1.25))

    turns: list[dict[str, Any]] = []
    if isinstance(speakers, dict):
        raw = speakers.get("turns") or []
        if isinstance(raw, list):
            turns = [t for t in raw if isinstance(t, dict)]

    cascade = _load_face_cascade() if enable_face else None
    if not enable_face:
        logger.info("Face detection gated off for this video type")
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return []

    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0) or 30.0
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        duration = (frame_count / fps) if fps > 0 else 0.0
        t_end = duration if end is None else min(end, duration)
        t_start = max(0.0, start)

        step = compute_frame_step(fps, sample_fps, frame_count, max_frames)
        samples: list[FocusRoi] = []
        idx = int(t_start * fps)
        end_idx = int(t_end * fps) if t_end > 0 else frame_count
        sampled = 0

        while idx < end_idx and sampled < max_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
            if not ok or frame is None:
                idx += step
                continue
            t = idx / fps
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces: list[tuple[int, int, int, int]] = []
            if cascade is not None:
                detected = cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.1,
                    minNeighbors=5,
                    minSize=(face_min, face_min),
                )
                faces = [(int(x), int(y), int(w), int(h)) for x, y, w, h in detected]

            motion_pts = _motion_points(analysis, t)
            active = _speaker_active(t, turns)
            rois = score_face_rois(
                faces,
                frame_w=width,
                frame_h=height,
                time_seconds=t,
                speaker_active=active,
                motion_pts=motion_pts,
                speaker_boost=speaker_boost,
                motion_boost=motion_boost,
            )
            if rois:
                samples.append(rois[0])
            elif motion_pts:
                mx, my, ms = max(motion_pts, key=lambda p: p[2])
                fw = width * 0.2
                fh = height * 0.2
                samples.append(
                    FocusRoi(
                        kind="object" if ms >= 0.5 else "motion",
                        x=max(0.0, mx * width - fw / 2),
                        y=max(0.0, my * height - fh / 2),
                        w=fw,
                        h=fh,
                        score=ms,
                        time_seconds=t,
                    )
                )
            else:
                small = cv2.resize(gray, (160, 90))
                band = _frame_motion_band(small)
                if band:
                    cx, cy, sc = band
                    fw = width * 0.25
                    fh = height * 0.25
                    samples.append(
                        FocusRoi(
                            kind="motion",
                            x=max(0.0, cx * width - fw / 2),
                            y=max(0.0, cy * height - fh / 2),
                            w=fw,
                            h=fh,
                            score=sc,
                            time_seconds=t,
                        )
                    )
                else:
                    samples.append(
                        FocusRoi(
                            kind="fallback_center",
                            x=width * 0.25,
                            y=height * 0.25,
                            w=width * 0.5,
                            h=height * 0.5,
                            score=0.01,
                            time_seconds=t,
                        )
                    )
            sampled += 1
            idx += step
        return samples
    finally:
        cap.release()


def pick_focus_point(roi: FocusRoi) -> tuple[float, float]:
    """Return focus centroid in pixel coordinates."""
    return (roi.x + roi.w / 2.0, roi.y + roi.h / 2.0)
