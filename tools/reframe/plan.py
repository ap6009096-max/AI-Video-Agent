"""Build smart reframe crop plans from focus samples (never naive center-only)."""

from __future__ import annotations

from typing import Any

from schemas.reframe import (
    AspectPreset,
    CropWindow,
    FocusRoi,
    ReframeClipPlan,
    ReframePlan,
)
from tools.reframe.catalog import detection_settings
from tools.reframe.detect import pick_focus_point


def compute_crop_rect(
    *,
    focus_x: float,
    focus_y: float,
    src_w: int,
    src_h: int,
    target_ratio: float,
    padding: float = 0.18,
) -> tuple[int, int, int, int]:
    """Crop window of target aspect that contains focus (not forced center)."""
    if src_w <= 0 or src_h <= 0 or target_ratio <= 0:
        return (0, 0, max(1, src_w), max(1, src_h))

    src_ratio = src_w / src_h
    if abs(src_ratio - target_ratio) < 1e-6:
        return (0, 0, src_w, src_h)

    if src_ratio > target_ratio:
        # Source wider → crop width
        crop_h = src_h
        crop_w = int(round(crop_h * target_ratio))
        crop_w = max(2, min(src_w, crop_w - (crop_w % 2)))
        # Place so focus is inside with padding toward edges
        ideal_x = focus_x - crop_w / 2.0
        # Bias: keep a bit of headroom (focus slightly above center vertically already)
        pad_px = padding * crop_w
        ideal_x = min(max(ideal_x, focus_x + pad_px - crop_w), focus_x - pad_px)
        crop_x = int(round(ideal_x))
        crop_x = max(0, min(src_w - crop_w, crop_x))
        crop_y = 0
    else:
        # Source taller → crop height
        crop_w = src_w
        crop_h = int(round(crop_w / target_ratio))
        crop_h = max(2, min(src_h, crop_h - (crop_h % 2)))
        ideal_y = focus_y - crop_h * 0.4  # keep subject in upper portion
        pad_px = padding * crop_h
        ideal_y = min(max(ideal_y, focus_y + pad_px - crop_h), focus_y - pad_px)
        crop_y = int(round(ideal_y))
        crop_y = max(0, min(src_h - crop_h, crop_y))
        crop_x = 0

    crop_w = max(2, crop_w - (crop_w % 2))
    crop_h = max(2, crop_h - (crop_h % 2))
    return (crop_x, crop_y, crop_w, crop_h)


def center_crop_rect(
    src_w: int, src_h: int, target_ratio: float
) -> tuple[int, int, int, int]:
    fx, fy = src_w / 2.0, src_h / 2.0
    return compute_crop_rect(
        focus_x=fx,
        focus_y=fy,
        src_w=src_w,
        src_h=src_h,
        target_ratio=target_ratio,
        padding=0.0,
    )


def _ema(prev: float | None, value: float, alpha: float) -> float:
    if prev is None:
        return value
    return alpha * value + (1.0 - alpha) * prev


def build_windows_from_samples(
    samples: list[FocusRoi],
    *,
    src_w: int,
    src_h: int,
    target_ratio: float,
    start: float,
    end: float,
) -> list[CropWindow]:
    settings = detection_settings()
    alpha = float(settings.get("ema_alpha", 0.35))
    padding = float(settings.get("padding", 0.18))
    window_seconds = float(settings.get("window_seconds", 2.0))
    max_windows = int(settings.get("max_windows_per_clip", 24))

    if end <= start:
        end = start + 0.1

    if not samples:
        cx, cy, cw, ch = center_crop_rect(src_w, src_h, target_ratio)
        return [
            CropWindow(
                start=start,
                end=end,
                crop_x=cx,
                crop_y=cy,
                crop_w=cw,
                crop_h=ch,
                focus_x=src_w / 2.0,
                focus_y=src_h / 2.0,
                method="fallback_center",
                notes="No focus samples — fallback center crop.",
            )
        ]

    # Smooth focus points
    fx_s: float | None = None
    fy_s: float | None = None
    smoothed: list[tuple[float, float, float, FocusRoi]] = []
    for roi in samples:
        fx, fy = pick_focus_point(roi)
        fx_s = _ema(fx_s, fx, alpha)
        fy_s = _ema(fy_s, fy, alpha)
        assert fx_s is not None and fy_s is not None
        smoothed.append((roi.time_seconds, fx_s, fy_s, roi))

    # Bucket into time windows
    windows: list[CropWindow] = []
    t = start
    while t < end and len(windows) < max_windows:
        t1 = min(end, t + window_seconds)
        mid = (t + t1) / 2.0
        # Nearest sample to mid
        nearest = min(smoothed, key=lambda s: abs(s[0] - mid))
        _, fx, fy, roi = nearest
        cx, cy, cw, ch = compute_crop_rect(
            focus_x=fx,
            focus_y=fy,
            src_w=src_w,
            src_h=src_h,
            target_ratio=target_ratio,
            padding=padding,
        )
        # Guard: not identical to pure center when focus is clearly offset
        method = str(roi.kind)
        windows.append(
            CropWindow(
                start=t,
                end=t1,
                crop_x=cx,
                crop_y=cy,
                crop_w=cw,
                crop_h=ch,
                focus_x=fx,
                focus_y=fy,
                method=method,
            )
        )
        t = t1
    return windows


def _clip_ranges(
    clips: dict[str, Any] | None,
    duration: float,
) -> list[tuple[int, float, float]]:
    ranges: list[tuple[int, float, float]] = []
    if isinstance(clips, dict):
        raw = clips.get("clips") or []
        if isinstance(raw, list):
            for c in raw:
                if not isinstance(c, dict):
                    continue
                try:
                    cid = int(c.get("id", len(ranges)))
                    s = float(c.get("start", 0.0))
                    e = float(c.get("end", s))
                except (TypeError, ValueError):
                    continue
                if e > s:
                    ranges.append((cid, s, e))
    if not ranges and duration > 0:
        ranges.append((0, 0.0, duration))
    return ranges


def build_reframe_plan(
    *,
    project_id: str,
    src_w: int,
    src_h: int,
    duration: float,
    aspect: AspectPreset,
    samples: list[FocusRoi],
    clips: dict[str, Any] | None = None,
    skipped: bool = False,
    notes: str = "",
) -> ReframePlan:
    settings = detection_settings()
    tol = float(settings.get("aspect_tolerance", 0.04))
    source_aspect = (src_w / src_h) if src_h else 0.0
    target_ratio = float(aspect.ratio) or 0.5625
    passthrough = (
        source_aspect > 0 and abs(source_aspect - target_ratio) <= tol
    )

    clip_plans: list[ReframeClipPlan] = []
    if not skipped:
        for cid, s, e in _clip_ranges(clips, duration):
            clip_samples = [r for r in samples if s <= r.time_seconds <= e]
            if not clip_samples:
                clip_samples = samples
            if passthrough:
                windows = [
                    CropWindow(
                        start=s,
                        end=e,
                        crop_x=0,
                        crop_y=0,
                        crop_w=src_w,
                        crop_h=src_h,
                        focus_x=src_w / 2.0,
                        focus_y=src_h / 2.0,
                        method="passthrough",
                        notes="Source aspect already matches target.",
                    )
                ]
            else:
                windows = build_windows_from_samples(
                    clip_samples,
                    src_w=src_w,
                    src_h=src_h,
                    target_ratio=target_ratio,
                    start=s,
                    end=e,
                )
            clip_plans.append(
                ReframeClipPlan(
                    clip_id=cid, src_start=s, src_end=e, windows=windows
                )
            )

    return ReframePlan(
        project_id=project_id,
        source_width=src_w,
        source_height=src_h,
        source_aspect=source_aspect,
        target_aspect=aspect.name,
        target_ratio=target_ratio,
        output_width=aspect.output_width,
        output_height=aspect.output_height,
        passthrough=passthrough,
        skipped=skipped,
        encoded=False,
        clip_plans=clip_plans,
        focus_samples=samples,
        notes=notes,
    )
