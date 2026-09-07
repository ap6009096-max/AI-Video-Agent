"""Smart reframing detection, planning, and FFmpeg render tools."""

from tools.reframe.catalog import (
    clear_reframe_cache,
    default_aspect_for_platform,
    detection_settings,
    list_aspects,
    resolve_aspect,
    resolve_target_aspect,
)
from tools.reframe.detect import (
    detect_focus_samples,
    pick_focus_point,
    score_face_rois,
)
from tools.reframe.plan import (
    build_reframe_plan,
    build_windows_from_samples,
    center_crop_rect,
    compute_crop_rect,
)
from tools.reframe.render import render_reframe

__all__ = [
    "build_reframe_plan",
    "build_windows_from_samples",
    "center_crop_rect",
    "clear_reframe_cache",
    "compute_crop_rect",
    "default_aspect_for_platform",
    "detect_focus_samples",
    "detection_settings",
    "list_aspects",
    "pick_focus_point",
    "render_reframe",
    "resolve_aspect",
    "resolve_target_aspect",
    "score_face_rois",
]
