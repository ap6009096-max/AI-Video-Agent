"""AI Creator Operating System — stage registry and capability presets."""

from __future__ import annotations

from typing import Any

from schemas.job import ProgressStepStatus

# Ordered Creator OS stages (UI / product surface).
# Analytics precedes Publishing Preparation to match LangGraph order
# (analytics node runs before render/export).
CREATOR_OS_STAGES: tuple[tuple[str, str], ...] = (
    ("research", "Research"),
    ("planning", "Planning"),
    ("script", "Script"),
    ("storyboard", "Storyboard"),
    ("video_creation", "Video Creation"),
    ("optimization", "Optimization"),
    ("analytics", "Analytics"),
    ("publishing_preparation", "Publishing Preparation"),
)

STAGE_IDS: tuple[str, ...] = tuple(s[0] for s in CREATOR_OS_STAGES)
STAGE_LABELS: dict[str, str] = {sid: label for sid, label in CREATOR_OS_STAGES}

# Map every LangGraph STEP_NODE_NAMES entry → Creator OS stage
NODE_TO_STAGE: dict[str, str] = {
    # Research
    "input_agent": "research",
    "youtube_ingest": "research",
    "local_video_ingest": "research",
    "script_ingest": "research",
    "step_02_transcript_extracted": "research",
    "transcript": "research",
    "video_understanding": "research",
    "scene_detection": "research",
    "audio_analysis": "research",
    "speaker_analysis": "research",
    "moment_detection": "research",
    "funny_moment": "research",
    "viral_moment": "research",
    "smart_clip": "research",
    "podcast": "research",
    "research": "research",
    "supervisor": "research",
    "shared_ai_analysis": "research",
    "object_detection": "research",
    # Planning
    "story": "planning",
    "video_type": "planning",
    "visual_style": "planning",
    "environment": "planning",
    "character": "planning",
    "camera": "planning",
    "director": "planning",
    "documentary": "planning",
    "brand": "planning",
    "content_calendar": "planning",
    # Script (+ localization)
    "script": "script",
    "country": "script",
    "regional": "script",
    "language": "script",
    "cultural": "script",
    "humor": "script",
    # Storyboard
    "storyboard": "storyboard",
    "image_generation": "storyboard",
    "motion_graphics": "storyboard",
    # Video Creation
    "video_generation": "video_creation",
    "b_roll": "video_creation",
    "voice": "video_creation",
    "avatar": "video_creation",
    "music": "video_creation",
    "captions": "video_creation",
    "smart_reframe": "video_creation",
    "render": "video_creation",
    "quality": "video_creation",
    # Optimization
    "platform": "optimization",
    "seo": "optimization",
    "trend": "optimization",
    "competitor": "optimization",
    "repurpose": "optimization",
    "thumbnail": "optimization",
    # Publishing Preparation
    "export": "publishing_preparation",
    # Analytics
    "analytics": "analytics",
}

# Pack keys that signal a stage has produced artifacts
STAGE_SIGNAL_PACKS: dict[str, tuple[str, ...]] = {
    "research": (
        "transcript",
        "clips",
        "podcast_clips",
        "research_report",
        "supervisor_crew",
        "moments",
    ),
    "planning": (
        "stories",
        "video_type_pack",
        "visual_style_pack",
        "environment_pack",
        "character_pack",
        "camera_pack",
        "director_pack",
        "documentary_pack",
        "brand_pack",
        "calendar_pack",
    ),
    "script": (
        "scripts",
        "locale_pack",
        "localizations",
        "cultural_adaptation",
        "humor_localization",
    ),
    "storyboard": (
        "storyboard_pack",
        "image_pack",
        "motion_graphics_pack",
    ),
    "video_creation": (
        "video_generation_pack",
        "broll_pack",
        "voice_pack",
        "avatar_pack",
        "music_pack",
        "captions_pack",
        "reframe_pack",
        "render_pack",
        "quality_pack",
    ),
    "optimization": (
        "platform_pack",
        "seo_pack",
        "trend_pack",
        "repurpose_pack",
        "thumbnail_pack",
    ),
    "analytics": ("analytics_pack",),
    "publishing_preparation": ("export_pack",),
}

# Creator OS feature preset (merge onto FeatureFlags defaults)
CREATOR_CAPABILITY_PRESET: dict[str, bool] = {
    "smart_clip_detection": True,
    "captions": True,
    "platform_optimization": True,
    "research": True,
    "storyboard": True,
    "video_generation": True,
    "seo": True,
    "thumbnail": True,
    "content_calendar": True,
    "analytics": True,
}


def stage_for_node(node: str) -> str | None:
    """Return Creator OS stage id for a graph node name, if known."""
    key = (node or "").strip()
    if not key:
        return None
    if key in NODE_TO_STAGE:
        return NODE_TO_STAGE[key]
    # Tolerate UI milestone labels / aliases
    lowered = key.lower().replace(" ", "_")
    return NODE_TO_STAGE.get(lowered)


def _stage_index(stage_id: str) -> int:
    try:
        return STAGE_IDS.index(stage_id)
    except ValueError:
        return -1


def _pack_present(state: dict[str, Any], key: str) -> bool:
    val = state.get(key)
    if val is None:
        return False
    if isinstance(val, dict) and not val:
        return False
    return True


def _highest_stage_from_packs(state: dict[str, Any]) -> int:
    highest = -1
    for sid in STAGE_IDS:
        packs = STAGE_SIGNAL_PACKS.get(sid) or ()
        if any(_pack_present(state, p) for p in packs):
            highest = max(highest, _stage_index(sid))
    return highest


def stage_progress_from_state(state: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Derive Creator OS stage checklist from workflow state.

    Status values mirror ProgressStepStatus: pending | running | completed | failed.
    """
    state = state if isinstance(state, dict) else {}
    job_status = str(state.get("status") or "").lower()
    error = state.get("error")

    last_node = str(state.get("last_node") or "").strip()
    # Infer last_node from messages / running UI step when absent
    if not last_node:
        steps = state.get("steps") or []
        for step in steps:
            if isinstance(step, dict) and step.get("status") == ProgressStepStatus.RUNNING.value:
                last_node = str(step.get("label") or "")
                break

    current_stage = stage_for_node(last_node) if last_node else None
    current_idx = _stage_index(current_stage) if current_stage else -1
    pack_idx = _highest_stage_from_packs(state)

    # Advance cursor to the furthest of pack evidence vs last_node stage
    cursor = max(current_idx, pack_idx)

    if job_status == "completed":
        return [
            {
                "id": sid,
                "label": STAGE_LABELS[sid],
                "status": ProgressStepStatus.COMPLETED.value,
            }
            for sid in STAGE_IDS
        ]

    failed_stage = current_stage if job_status == "failed" and current_stage else None

    out: list[dict[str, Any]] = []
    for i, sid in enumerate(STAGE_IDS):
        label = STAGE_LABELS[sid]
        if failed_stage and sid == failed_stage:
            status = ProgressStepStatus.FAILED.value
        elif job_status == "failed" and failed_stage and i < _stage_index(failed_stage):
            status = ProgressStepStatus.COMPLETED.value
        elif cursor < 0:
            status = (
                ProgressStepStatus.RUNNING.value
                if job_status == "running" and i == 0
                else ProgressStepStatus.PENDING.value
            )
        elif i < cursor:
            status = ProgressStepStatus.COMPLETED.value
        elif i == cursor:
            if job_status == "running":
                status = ProgressStepStatus.RUNNING.value
            elif job_status == "failed":
                status = ProgressStepStatus.FAILED.value
            else:
                status = ProgressStepStatus.COMPLETED.value
        else:
            status = ProgressStepStatus.PENDING.value
        if error and job_status == "failed" and status == ProgressStepStatus.RUNNING.value:
            status = ProgressStepStatus.FAILED.value
        out.append({"id": sid, "label": label, "status": status})
    return out


def apply_creator_os_preset(features: dict[str, Any] | None = None) -> dict[str, bool]:
    """Merge Creator OS capability preset onto FeatureFlags-compatible dict."""
    from schemas.job import FeatureFlags

    base = FeatureFlags().model_dump()
    if isinstance(features, dict):
        for k, v in features.items():
            if k in base and isinstance(v, bool):
                base[k] = v
    base.update(CREATOR_CAPABILITY_PRESET)
    return {k: bool(v) for k, v in base.items()}
