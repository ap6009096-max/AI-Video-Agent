"""Sampled scene / visual-change detection with OpenCV."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from config.settings import get_settings
from core.errors import VideoUnderstandingError
from core.logging import get_logger
from schemas.analysis import (
    ObjectCue,
    SampledFrameInfo,
    SceneSegment,
    VisualChange,
)
from tools.video.probe import compute_frame_step

logger = get_logger(__name__)


def _dominant_colors(frame_bgr: Any, k: int = 3) -> list[tuple[int, int, int]]:
    """Return up to k dominant RGB colors from a downscaled frame."""
    try:
        import cv2  # type: ignore
    except ImportError:
        return []

    small = cv2.resize(frame_bgr, (64, 64), interpolation=cv2.INTER_AREA)
    data = small.reshape((-1, 3)).astype(np.float32)
    if len(data) < k:
        return []
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
    _compactness, labels, centers = cv2.kmeans(
        data, k, None, criteria, 3, cv2.KMEANS_PP_CENTERS
    )
    centers_u8 = centers.astype(np.uint8)
    # OpenCV is BGR
    return [(int(c[2]), int(c[1]), int(c[0])) for c in centers_u8]


def analyze_scenes(
    media_path: str | Path,
    *,
    sample_fps: float | None = None,
    scene_threshold: float | None = None,
    max_frames: int | None = None,
) -> dict[str, Any]:
    """Sample frames and detect scene cuts / motion without full-frame processing."""
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise VideoUnderstandingError(
            "opencv-python-headless is not installed. Run: pip install opencv-python-headless"
        ) from exc

    settings = get_settings()
    sf = sample_fps if sample_fps is not None else settings.analysis_sample_fps
    thr = scene_threshold if scene_threshold is not None else settings.analysis_scene_threshold
    mf = max_frames if max_frames is not None else settings.analysis_max_frames

    path = Path(media_path)
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise VideoUnderstandingError(f"OpenCV could not open video: {path}")

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0) or 30.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    step = compute_frame_step(fps, sf, frame_count, mf)

    sampled: list[SampledFrameInfo] = []
    changes: list[VisualChange] = []
    cut_times: list[tuple[float, float]] = []
    object_cues: list[ObjectCue] = []

    prev_gray = None
    idx = 0
    analyzed = 0

    try:
        while True:
            if frame_count > 0 and idx >= frame_count:
                break
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
            if not ok or frame is None:
                break

            time_s = idx / fps if fps > 0 else float(idx)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray_small = cv2.resize(gray, (160, 90), interpolation=cv2.INTER_AREA)
            motion = 0.0
            if prev_gray is not None:
                diff = cv2.absdiff(gray_small, prev_gray)
                motion = float(np.mean(diff) / 255.0)
                if motion >= thr:
                    changes.append(
                        VisualChange(time_seconds=time_s, score=motion, kind="cut")
                    )
                    cut_times.append((time_s, motion))
                elif motion >= thr * 0.5:
                    changes.append(
                        VisualChange(time_seconds=time_s, score=motion, kind="motion")
                    )

            colors = _dominant_colors(frame) if analyzed % 5 == 0 else []
            sampled.append(
                SampledFrameInfo(
                    frame_index=idx,
                    time_seconds=time_s,
                    motion_score=motion,
                    dominant_colors=colors,
                )
            )
            if motion >= thr:
                object_cues.append(
                    ObjectCue(
                        label="motion_hotspot",
                        time_seconds=time_s,
                        detail=f"motion_score={motion:.3f}",
                    )
                )
            if colors:
                object_cues.append(
                    ObjectCue(
                        label="color_cluster",
                        time_seconds=time_s,
                        detail=f"colors={colors[:3]}",
                    )
                )

            prev_gray = gray_small
            analyzed += 1
            idx += step
            if analyzed >= mf:
                break
    finally:
        cap.release()

    duration = (frame_count / fps) if fps > 0 and frame_count > 0 else (
        sampled[-1].time_seconds if sampled else 0.0
    )
    scenes = _build_scenes(cut_times, duration)
    logger.info(
        "Scene analysis media=%s frames_analyzed=%s step=%s scenes=%s",
        path.name,
        analyzed,
        step,
        len(scenes),
    )
    return {
        "sampled_frames": sampled,
        "scenes": scenes,
        "visual_changes": changes,
        "object_cues": object_cues[:50],
        "frames_analyzed": analyzed,
        "sample_step": step,
        "effective_sample_fps": (fps / step) if step else sf,
    }


def _build_scenes(
    cut_times: list[tuple[float, float]],
    duration: float,
) -> list[SceneSegment]:
    boundaries = [0.0] + [t for t, _ in cut_times] + ([duration] if duration > 0 else [])
    # Deduplicate close boundaries
    cleaned: list[float] = []
    for t in boundaries:
        if not cleaned or abs(t - cleaned[-1]) > 0.15:
            cleaned.append(t)
    if len(cleaned) < 2:
        end = duration if duration > 0 else 0.0
        return [SceneSegment(id=0, start=0.0, end=end, score=0.0)]

    scenes: list[SceneSegment] = []
    score_by_time = {t: s for t, s in cut_times}
    for i in range(len(cleaned) - 1):
        start = cleaned[i]
        end = cleaned[i + 1]
        scenes.append(
            SceneSegment(
                id=i,
                start=start,
                end=end,
                score=float(score_by_time.get(end, score_by_time.get(start, 0.0))),
            )
        )
    return scenes
