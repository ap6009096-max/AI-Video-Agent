"""Face-detection gate by video type (Rule 7)."""

from __future__ import annotations

from typing import Any

# Video types where Haar / face ROI is useful
FACE_ENABLED_TYPES = frozenset(
    {
        "talking_head",
        "talking head",
        "interview",
        "podcast",
        "webinar",
        "ai_avatar",
        "ai avatar",
        "avatar",
        "testimonial",
        "vlog",
    }
)

FACE_SKIP_TYPES = frozenset(
    {
        "animation",
        "screen_recording",
        "screen recording",
        "screencast",
        "motion_graphics",
        "motion graphics",
        "text_on_screen",
        "text on screen",
    }
)


def _norm(value: str) -> str:
    return " ".join((value or "").strip().lower().replace("-", " ").replace("_", " ").split())


def extract_video_type_label(
    video_type_pack: dict[str, Any] | None = None,
    *,
    config_video_type: str | None = None,
) -> str:
    if config_video_type:
        return str(config_video_type)
    if not isinstance(video_type_pack, dict):
        return ""
    preset = video_type_pack.get("preset") or video_type_pack.get("plan") or {}
    if isinstance(preset, dict):
        return str(
            preset.get("name")
            or preset.get("id")
            or video_type_pack.get("source_label")
            or ""
        )
    return str(video_type_pack.get("source_label") or "")


def should_run_face_detection(
    video_type: str | None = None,
    *,
    video_type_pack: dict[str, Any] | None = None,
    default_when_unknown: bool = True,
) -> bool:
    """Return True when face/Haar detection should run for this video type."""
    label = _norm(video_type or extract_video_type_label(video_type_pack))
    if not label:
        return default_when_unknown
    compact = label.replace(" ", "_")
    spaced = label
    if compact in FACE_SKIP_TYPES or spaced in FACE_SKIP_TYPES:
        return False
    if any(s in spaced for s in ("animation", "screen recording", "screencast")):
        return False
    if compact in FACE_ENABLED_TYPES or spaced in FACE_ENABLED_TYPES:
        return True
    if any(
        token in spaced
        for token in (
            "talking head",
            "interview",
            "podcast",
            "webinar",
            "avatar",
            "testimonial",
        )
    ):
        return True
    return default_when_unknown
