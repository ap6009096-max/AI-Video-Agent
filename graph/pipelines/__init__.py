"""Pipeline segment registry and hooks for nested Creator OS."""

from __future__ import annotations

from typing import Any, Callable

from core.logging import get_logger

logger = get_logger(__name__)

PIPELINE_NAMES: tuple[str, ...] = (
    "input_pipeline",
    "analysis_pipeline",
    "content_pipeline",
    "localization_pipeline",
    "render_pipeline",
    "growth_pipeline",
)

# Existing STEP nodes grouped by nested pipeline (documentation + tests)
PIPELINE_NODE_GROUPS: dict[str, tuple[str, ...]] = {
    "input_pipeline": (
        "input_agent",
        "youtube_ingest",
        "local_video_ingest",
        "script_ingest",
    ),
    "analysis_pipeline": (
        "transcript",
        "step_02_transcript_extracted",
        "video_understanding",
        "scene_detection",
        "audio_analysis",
        "speaker_analysis",
        "moment_detection",
        "funny_moment",
        "viral_moment",
        "smart_clip",
        "podcast",
        "research",
        "supervisor",
        "shared_ai_analysis",
        "object_detection",
    ),
    "content_pipeline": (
        "story",
        "script",
        "video_type",
        "visual_style",
        "environment",
        "storyboard",
        "character",
        "camera",
        "director",
        "motion_graphics",
        "documentary",
        "video_generation",
        "image_generation",
        "brand",
        "content_calendar",
    ),
    "localization_pipeline": (
        "country",
        "regional",
        "language",
        "cultural",
        "humor",
    ),
    "render_pipeline": (
        "b_roll",
        "voice",
        "avatar",
        "music",
        "captions",
        "smart_reframe",
        "render",
        "quality",
        "export",
    ),
    "growth_pipeline": (
        "platform",
        "seo",
        "trend",
        "competitor",
        "repurpose",
        "thumbnail",
        "analytics",
    ),
}


def pipeline_hook(name: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Return a node that records pipeline entry (used by nested main graph)."""

    def _node(state: dict[str, Any]) -> dict[str, Any]:
        messages = list(state.get("messages") or [])
        messages.append(f"[pipeline] enter {name}")
        logger.info("Entering pipeline %s", name)
        return {"messages": messages, "current_pipeline": name}

    return _node
