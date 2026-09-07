"""Project flat state projection for UI / export result."""

from __future__ import annotations

from typing import Any


def _get(d: dict[str, Any] | None, *keys: str, default: Any = None) -> Any:
    cur: Any = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
    return default if cur is None else cur


def project_state_view(state: dict[str, Any]) -> dict[str, Any]:
    """Flatten WorkflowState into the PROMPT 25 result surface."""
    job = state.get("job") or {}
    project = state.get("project") or {}
    config = job.get("config") or {}
    source_meta = state.get("source_metadata") or {}
    analysis = state.get("analysis") or {}
    props = analysis.get("properties") if isinstance(analysis, dict) else {}
    if not isinstance(props, dict):
        props = {}

    render_pack = state.get("render_pack") or {}
    render_plan = (
        render_pack.get("plan") if isinstance(render_pack, dict) else None
    ) or {}
    quality_pack = state.get("quality_pack") or {}
    quality_report = (
        quality_pack.get("report") if isinstance(quality_pack, dict) else None
    ) or quality_pack
    export_pack = state.get("export_pack") or {}
    captions_pack = state.get("captions_pack") or {}
    platform_pack = state.get("platform_pack") or {}

    video_path = ""
    if isinstance(render_plan, dict):
        video_path = str(render_plan.get("output_path") or "")
    if not video_path and isinstance(export_pack, dict):
        video_path = str(export_pack.get("export_path") or "")
    if not video_path:
        video_path = str(
            source_meta.get("local_path")
            or source_meta.get("media_path")
            or project.get("source_path")
            or ""
        )

    duration = props.get("duration_seconds") or source_meta.get("duration") or 0.0
    try:
        duration = float(duration or 0.0)
    except (TypeError, ValueError):
        duration = 0.0

    output_files = {}
    if isinstance(export_pack, dict):
        output_files = dict(export_pack.get("output_files") or {})
        bundle = export_pack.get("bundle") or {}
        if isinstance(bundle, dict) and not output_files:
            output_files = {
                "video": bundle.get("video_path") or "",
                "thumbnail": bundle.get("thumbnail_path") or "",
                "captions": list(bundle.get("caption_paths") or []),
                "platform_metadata": bundle.get("platform_metadata_path") or "",
                "manifest": bundle.get("manifest_path") or "",
            }

    errors = state.get("error")
    from schemas.creator_os import stage_for_node, stage_progress_from_state

    stages = stage_progress_from_state(state)
    last_node = str(state.get("last_node") or "")
    return {
        "project_id": project.get("project_id") or job.get("job_id"),
        "source_type": project.get("source_type") or job.get("source_type"),
        "source_path": project.get("source_path") or job.get("upload_path") or "",
        "youtube_url": project.get("youtube_url") or job.get("youtube_url") or "",
        "raw_text": project.get("raw_text") or job.get("script_text") or "",
        "video_path": video_path,
        "duration": duration,
        "creator_os_stages": stages,
        "last_stage": stage_for_node(last_node),
        "transcript": state.get("transcript") or state.get("speech_transcript"),
        "scenes": state.get("scenes"),
        "audio_analysis": state.get("audio_analysis"),
        "speakers": state.get("speakers"),
        "moments": state.get("moments"),
        "selected_clips": state.get("clips"),
        "podcast_clips": state.get("podcast_clips"),
        "research_report": state.get("research_report"),
        "supervisor_crew": state.get("supervisor_crew"),
        "delegation_log": state.get("delegation_log"),
        "task_board": state.get("task_board"),
        "story": state.get("stories"),
        "script": state.get("scripts"),
        "country": state.get("country_profile") or config.get("country"),
        "region": state.get("region_profile") or config.get("region"),
        "language": _get(state.get("locale_pack"), "language")
        or config.get("language"),
        "cultural_context": state.get("cultural_adaptation"),
        "humor_context": state.get("humor_localization"),
        "video_type": state.get("video_type_pack") or config.get("video_type"),
        "visual_style": state.get("visual_style_pack") or config.get("visual_style"),
        "environment": state.get("environment_pack") or config.get("environment"),
        "storyboard": state.get("storyboard_pack"),
        "character": state.get("character_pack"),
        "camera": state.get("camera_pack"),
        "director": state.get("director_pack"),
        "motion_graphics": state.get("motion_graphics_pack"),
        "documentary": state.get("documentary_pack"),
        "video_generation": state.get("video_generation_pack"),
        "image": state.get("image_pack"),
        "platform": state.get("platform_pack") or config.get("platform"),
        "brand": state.get("brand_pack"),
        "voice": state.get("voice_pack") or config.get("voice"),
        "avatar": state.get("avatar_pack") or config.get("avatar"),
        "music": state.get("music_pack") or config.get("music"),
        "thumbnail": state.get("thumbnail_pack"),
        "seo": state.get("seo_pack"),
        "trend": state.get("trend_pack"),
        "repurpose": state.get("repurpose_pack"),
        "content_calendar": state.get("calendar_pack"),
        "analytics": state.get("analytics_pack"),
        "captions": captions_pack,
        "render_plan": render_plan if render_plan else render_pack,
        "output_files": output_files,
        "quality_report": quality_report,
        "errors": [errors] if errors else [],
        "progress": state.get("steps") or [],
        "localizations": state.get("localizations"),
        "export_pack": export_pack,
        "platform_metadata": _get(platform_pack, "plan", "metadata"),
        "project_dir": state.get("project_dir"),
    }
