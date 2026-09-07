"""Tests for video probe sampling helpers and scene analysis."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest

from tools.video.probe import compute_frame_step
from tools.video.scenes import analyze_scenes


def test_compute_frame_step_respects_sample_fps() -> None:
    step = compute_frame_step(video_fps=30.0, sample_fps=1.0, frame_count=300, max_frames=900)
    assert step == 30


def test_compute_frame_step_respects_max_frames() -> None:
    # 30fps * 3600s = 108000 frames; sample_fps=1 => step 30 => 3600 projected > 100 max
    step = compute_frame_step(video_fps=30.0, sample_fps=1.0, frame_count=108_000, max_frames=100)
    assert step >= 30
    projected = 108_000 // step
    assert projected <= 100 + 5  # allow small rounding slack


def test_analyze_scenes_detects_cut_with_mock_capture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Synthetic frame diffs: dark then bright => cut at sample boundary."""
    import tools.video.scenes as scenes_mod

    frames = []
    for i in range(0, 90, 30):  # indices 0, 30, 60 at step=30 for 30fps/1fps
        if i < 60:
            frames.append(np.zeros((90, 160, 3), dtype=np.uint8))
        else:
            frames.append(np.full((90, 160, 3), 255, dtype=np.uint8))

    class FakeCap:
        def __init__(self) -> None:
            self._pos = 0
            self._opened = True

        def isOpened(self) -> bool:
            return self._opened

        def get(self, prop: int) -> float:
            # CAP_PROP_FPS=5, CAP_PROP_FRAME_COUNT=7 in OpenCV
            if prop == 5:
                return 30.0
            if prop == 7:
                return 90.0
            return 0.0

        def set(self, _prop: int, value: float) -> bool:
            self._pos = int(value)
            return True

        def read(self):
            # Map absolute frame index to our sampled list via position
            if self._pos >= 90:
                return False, None
            # Build frame on the fly from position
            if self._pos < 60:
                frame = np.zeros((180, 320, 3), dtype=np.uint8)
            else:
                frame = np.full((180, 320, 3), 255, dtype=np.uint8)
            return True, frame

        def release(self) -> None:
            self._opened = False

    fake_cv2 = MagicMock()
    fake_cv2.VideoCapture = lambda *_a, **_k: FakeCap()
    fake_cv2.CAP_PROP_FPS = 5
    fake_cv2.CAP_PROP_FRAME_COUNT = 7
    fake_cv2.CAP_PROP_POS_FRAMES = 1
    fake_cv2.COLOR_BGR2GRAY = 6
    fake_cv2.INTER_AREA = 3

    def _cvtColor(frame, _code):
        return frame[:, :, 0].copy() if frame.ndim == 3 else frame

    def _resize(img, size, interpolation=None):
        h, w = size[1], size[0]
        return np.zeros((h, w), dtype=np.uint8) if img.ndim == 2 else np.zeros((h, w, 3), dtype=np.uint8)

    def _absdiff(a, b):
        return np.abs(a.astype(np.int16) - b.astype(np.int16)).astype(np.uint8)

    # Proper resize that preserves intensity for cut detection
    def _resize_real(img, size, interpolation=None):
        # size is (width, height)
        w, h = size
        if img.ndim == 2:
            # nearest: take mean intensity of source
            val = int(np.mean(img))
            return np.full((h, w), val, dtype=np.uint8)
        val = int(np.mean(img))
        out = np.full((h, w, img.shape[2]), val, dtype=np.uint8)
        return out

    fake_cv2.cvtColor = _cvtColor
    fake_cv2.resize = _resize_real
    fake_cv2.absdiff = _absdiff
    fake_cv2.TERM_CRITERIA_EPS = 1
    fake_cv2.TERM_CRITERIA_MAX_ITER = 2
    fake_cv2.KMEANS_PP_CENTERS = 2

    def _kmeans(*_a, **_k):
        centers = np.array([[0, 0, 0], [128, 128, 128], [255, 255, 255]], dtype=np.float32)
        labels = np.zeros((64 * 64, 1), dtype=np.int32)
        return 0.0, labels, centers

    fake_cv2.kmeans = _kmeans

    monkeypatch.setitem(__import__("sys").modules, "cv2", fake_cv2)
    # Force re-import path inside analyze_scenes via import cv2
    monkeypatch.setattr(
        scenes_mod,
        "analyze_scenes",
        scenes_mod.analyze_scenes,
    )

    result = analyze_scenes(
        "fake.mp4",
        sample_fps=1.0,
        scene_threshold=0.2,
        max_frames=900,
    )
    assert result["frames_analyzed"] == 3  # 0, 30, 60
    assert result["visual_changes"]
    assert any(c.kind == "cut" for c in result["visual_changes"])
    assert result["scenes"]
