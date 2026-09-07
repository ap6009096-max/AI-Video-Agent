"""Project and output directory path helpers."""

from __future__ import annotations

from pathlib import Path

from core.errors import StorageError
from core.logging import get_logger

logger = get_logger(__name__)


def get_project_root() -> Path:
    """Return the repository root (parent of the `core` package)."""
    return Path(__file__).resolve().parent.parent


def get_output_dir(output_dir: str | None = None) -> Path:
    """Resolve the output directory path (absolute)."""
    from config.settings import get_settings

    raw = output_dir if output_dir is not None else get_settings().output_dir
    path = Path(raw)
    if not path.is_absolute():
        path = get_project_root() / path
    return path.resolve()


def ensure_output_dir(output_dir: str | None = None) -> Path:
    """Create the output directory if it does not exist and return its path."""
    path = get_output_dir(output_dir)
    try:
        path.mkdir(parents=True, exist_ok=True)
        logger.debug("Output directory ready: %s", path)
    except OSError as exc:
        raise StorageError(f"Failed to create output directory: {path}") from exc
    return path


def ensure_uploads_dir(output_dir: str | None = None) -> Path:
    """Create and return ``OUTPUT_DIR/uploads`` for local video uploads."""
    uploads = ensure_output_dir(output_dir) / "uploads"
    try:
        uploads.mkdir(parents=True, exist_ok=True)
        logger.debug("Uploads directory ready: %s", uploads)
    except OSError as exc:
        raise StorageError(f"Failed to create uploads directory: {uploads}") from exc
    return uploads


def ensure_media_dir(output_dir: str | None = None) -> Path:
    """Create and return ``OUTPUT_DIR/media`` for staged upload/YouTube files."""
    media = ensure_output_dir(output_dir) / "media"
    try:
        media.mkdir(parents=True, exist_ok=True)
        logger.debug("Media directory ready: %s", media)
    except OSError as exc:
        raise StorageError(f"Failed to create media directory: {media}") from exc
    return media


def ensure_projects_dir(output_dir: str | None = None) -> Path:
    """Create and return ``OUTPUT_DIR/projects`` for per-job project folders."""
    projects = ensure_output_dir(output_dir) / "projects"
    try:
        projects.mkdir(parents=True, exist_ok=True)
        logger.debug("Projects directory ready: %s", projects)
    except OSError as exc:
        raise StorageError(f"Failed to create projects directory: {projects}") from exc
    return projects


def get_project_dir(project_id: str, output_dir: str | None = None) -> Path:
    """Return the absolute path for a project folder (may not exist yet)."""
    if not project_id or not str(project_id).strip():
        raise StorageError("project_id is required")
    safe_id = Path(str(project_id).strip()).name
    return (ensure_projects_dir(output_dir) / safe_id).resolve()


def ensure_project_dir(project_id: str, output_dir: str | None = None) -> Path:
    """Create ``OUTPUT_DIR/projects/{project_id}`` and return its path."""
    path = get_project_dir(project_id, output_dir)
    try:
        path.mkdir(parents=True, exist_ok=True)
        logger.debug("Project directory ready: %s", path)
    except OSError as exc:
        raise StorageError(f"Failed to create project directory: {path}") from exc
    return path


def ensure_project_source_dir(project_id: str, output_dir: str | None = None) -> Path:
    """Create and return ``OUTPUT_DIR/projects/{project_id}/source``."""
    source = ensure_project_dir(project_id, output_dir) / "source"
    try:
        source.mkdir(parents=True, exist_ok=True)
        logger.debug("Project source directory ready: %s", source)
    except OSError as exc:
        raise StorageError(f"Failed to create project source directory: {source}") from exc
    return source


def get_transcript_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return the path for ``projects/{project_id}/transcript.json`` (script path)."""
    return get_project_dir(project_id, output_dir) / "transcript.json"


def ensure_project_transcripts_dir(project_id: str, output_dir: str | None = None) -> Path:
    """Create and return ``OUTPUT_DIR/projects/{project_id}/transcripts``."""
    transcripts = ensure_project_dir(project_id, output_dir) / "transcripts"
    try:
        transcripts.mkdir(parents=True, exist_ok=True)
        logger.debug("Project transcripts directory ready: %s", transcripts)
    except OSError as exc:
        raise StorageError(f"Failed to create transcripts directory: {transcripts}") from exc
    return transcripts


def get_speech_transcript_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/transcripts/transcript.json`` (Whisper)."""
    return ensure_project_transcripts_dir(project_id, output_dir) / "transcript.json"


def ensure_project_analysis_dir(project_id: str, output_dir: str | None = None) -> Path:
    """Create and return ``OUTPUT_DIR/projects/{project_id}/analysis``."""
    analysis = ensure_project_dir(project_id, output_dir) / "analysis"
    try:
        analysis.mkdir(parents=True, exist_ok=True)
        logger.debug("Project analysis directory ready: %s", analysis)
    except OSError as exc:
        raise StorageError(f"Failed to create analysis directory: {analysis}") from exc
    return analysis


def get_video_analysis_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/video_analysis.json``."""
    return ensure_project_analysis_dir(project_id, output_dir) / "video_analysis.json"


def get_scenes_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/scenes.json``."""
    return ensure_project_analysis_dir(project_id, output_dir) / "scenes.json"


def get_audio_analysis_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/audio_analysis.json``."""
    return ensure_project_analysis_dir(project_id, output_dir) / "audio_analysis.json"


def get_speakers_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/speakers.json``."""
    return ensure_project_analysis_dir(project_id, output_dir) / "speakers.json"


def get_moments_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/moments.json``."""
    return ensure_project_analysis_dir(project_id, output_dir) / "moments.json"


def get_funny_moments_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/funny_moments.json``."""
    return ensure_project_analysis_dir(project_id, output_dir) / "funny_moments.json"


def get_viral_moments_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/viral_moments.json``."""
    return ensure_project_analysis_dir(project_id, output_dir) / "viral_moments.json"


def get_clips_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/clips.json``."""
    return ensure_project_analysis_dir(project_id, output_dir) / "clips.json"


def get_podcast_clips_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/podcast_clips.json``."""
    return ensure_project_analysis_dir(project_id, output_dir) / "podcast_clips.json"


def get_research_report_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/research_report.json``."""
    return ensure_project_analysis_dir(project_id, output_dir) / "research_report.json"


def get_supervisor_crew_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/supervisor_crew.json``."""
    return ensure_project_analysis_dir(project_id, output_dir) / "supervisor_crew.json"


def get_stories_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/stories.json``."""
    return ensure_project_analysis_dir(project_id, output_dir) / "stories.json"


def get_scripts_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/scripts.json``."""
    return ensure_project_analysis_dir(project_id, output_dir) / "scripts.json"


def get_locale_context_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/locale_context.json``."""
    return ensure_project_analysis_dir(project_id, output_dir) / "locale_context.json"


def get_localizations_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/localizations.json``."""
    return ensure_project_analysis_dir(project_id, output_dir) / "localizations.json"


def get_cultural_adaptation_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/cultural_adaptation.json``."""
    return (
        ensure_project_analysis_dir(project_id, output_dir) / "cultural_adaptation.json"
    )


def get_humor_localization_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/humor_localization.json``."""
    return (
        ensure_project_analysis_dir(project_id, output_dir) / "humor_localization.json"
    )


def get_video_type_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/video_type.json``."""
    return ensure_project_analysis_dir(project_id, output_dir) / "video_type.json"


def get_visual_style_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/visual_style.json``."""
    return ensure_project_analysis_dir(project_id, output_dir) / "visual_style.json"


def get_environment_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/environment.json``."""
    return ensure_project_analysis_dir(project_id, output_dir) / "environment.json"


def get_broll_plan_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/broll_plan.json``."""
    return ensure_project_analysis_dir(project_id, output_dir) / "broll_plan.json"


def get_voice_plan_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/voice_plan.json``."""
    return ensure_project_analysis_dir(project_id, output_dir) / "voice_plan.json"


def ensure_project_audio_dir(
    project_id: str, output_dir: str | None = None
) -> Path:
    """Ensure and return ``projects/{project_id}/audio/``."""
    path = get_project_dir(project_id, output_dir) / "audio"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_voice_audio_path(
    project_id: str, language_code: str, output_dir: str | None = None
) -> Path:
    """Return ``projects/{project_id}/audio/voice_{lang}.mp3``."""
    code = "".join(
        ch for ch in (language_code or "en").strip().lower() if ch.isalnum()
    ) or "en"
    return ensure_project_audio_dir(project_id, output_dir) / f"voice_{code}.mp3"


def get_music_plan_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/music_plan.json``."""
    return ensure_project_analysis_dir(project_id, output_dir) / "music_plan.json"


def get_avatar_plan_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/avatar_plan.json``."""
    return ensure_project_analysis_dir(project_id, output_dir) / "avatar_plan.json"


def get_thumbnail_plan_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/thumbnail_plan.json``."""
    return ensure_project_analysis_dir(project_id, output_dir) / "thumbnail_plan.json"


def get_seo_plan_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/seo_plan.json``."""
    return ensure_project_analysis_dir(project_id, output_dir) / "seo_plan.json"


def get_trend_plan_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/trend_plan.json``."""
    return ensure_project_analysis_dir(project_id, output_dir) / "trend_plan.json"


def get_repurpose_plan_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/repurpose_plan.json``."""
    return ensure_project_analysis_dir(project_id, output_dir) / "repurpose_plan.json"


def get_calendar_plan_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/calendar_plan.json``."""
    return ensure_project_analysis_dir(project_id, output_dir) / "calendar_plan.json"


def get_brand_plan_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/brand_plan.json``."""
    return ensure_project_analysis_dir(project_id, output_dir) / "brand_plan.json"


def get_analytics_plan_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/analytics_plan.json``."""
    return ensure_project_analysis_dir(project_id, output_dir) / "analytics_plan.json"


def ensure_project_images_dir(
    project_id: str, output_dir: str | None = None
) -> Path:
    """Ensure and return ``projects/{project_id}/images/``."""
    path = get_project_dir(project_id, output_dir) / "images"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_image_plan_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/image_plan.json``."""
    return ensure_project_analysis_dir(project_id, output_dir) / "image_plan.json"


def get_storyboard_plan_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/storyboard_plan.json``."""
    return ensure_project_analysis_dir(project_id, output_dir) / "storyboard_plan.json"


def get_video_generation_plan_path(
    project_id: str, output_dir: str | None = None
) -> Path:
    """Return ``projects/{project_id}/analysis/video_generation_plan.json``."""
    return (
        ensure_project_analysis_dir(project_id, output_dir)
        / "video_generation_plan.json"
    )


def get_director_plan_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/director_plan.json``."""
    return ensure_project_analysis_dir(project_id, output_dir) / "director_plan.json"


def get_character_plan_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/character_plan.json``."""
    return ensure_project_analysis_dir(project_id, output_dir) / "character_plan.json"


def get_camera_plan_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/camera_plan.json``."""
    return ensure_project_analysis_dir(project_id, output_dir) / "camera_plan.json"


def get_motion_graphics_plan_path(
    project_id: str, output_dir: str | None = None
) -> Path:
    """Return ``projects/{project_id}/analysis/motion_graphics_plan.json``."""
    return (
        ensure_project_analysis_dir(project_id, output_dir)
        / "motion_graphics_plan.json"
    )


def get_documentary_plan_path(
    project_id: str, output_dir: str | None = None
) -> Path:
    """Return ``projects/{project_id}/analysis/documentary_plan.json``."""
    return (
        ensure_project_analysis_dir(project_id, output_dir) / "documentary_plan.json"
    )


def ensure_project_captions_dir(
    project_id: str, output_dir: str | None = None
) -> Path:
    """Ensure and return ``projects/{project_id}/captions/``."""
    path = get_project_dir(project_id, output_dir) / "captions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_captions_dir(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/captions/`` (creates if missing)."""
    return ensure_project_captions_dir(project_id, output_dir)


def get_captions_plan_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/captions_plan.json``."""
    return ensure_project_analysis_dir(project_id, output_dir) / "captions_plan.json"


def ensure_project_renders_dir(
    project_id: str, output_dir: str | None = None
) -> Path:
    """Ensure and return ``projects/{project_id}/renders/``."""
    path = get_project_dir(project_id, output_dir) / "renders"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_renders_dir(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/renders/`` (creates if missing)."""
    return ensure_project_renders_dir(project_id, output_dir)


def get_reframe_plan_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/reframe_plan.json``."""
    return ensure_project_analysis_dir(project_id, output_dir) / "reframe_plan.json"


def ensure_project_exports_dir(
    project_id: str, output_dir: str | None = None
) -> Path:
    """Ensure and return ``projects/{project_id}/exports/``."""
    path = get_project_dir(project_id, output_dir) / "exports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_exports_dir(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/exports/`` (creates if missing)."""
    return ensure_project_exports_dir(project_id, output_dir)


def get_platform_plan_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/platform_plan.json``."""
    return ensure_project_analysis_dir(project_id, output_dir) / "platform_plan.json"


def get_platform_export_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/exports/platform_metadata.json``."""
    return ensure_project_exports_dir(project_id, output_dir) / "platform_metadata.json"


def get_render_plan_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/render_plan.json``."""
    return ensure_project_analysis_dir(project_id, output_dir) / "render_plan.json"


def get_quality_report_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/analysis/quality_report.json``."""
    return ensure_project_analysis_dir(project_id, output_dir) / "quality_report.json"


def get_export_manifest_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/exports/manifest.json``."""
    return ensure_project_exports_dir(project_id, output_dir) / "manifest.json"


def get_workflow_memory_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/memory.json``."""
    return ensure_project_dir(project_id, output_dir) / "memory.json"


def get_execution_history_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/execution_history.jsonl``."""
    return ensure_project_dir(project_id, output_dir) / "execution_history.jsonl"


def get_checkpoints_path(project_id: str, output_dir: str | None = None) -> Path:
    """Return ``projects/{project_id}/checkpoints.sqlite``."""
    return ensure_project_dir(project_id, output_dir) / "checkpoints.sqlite"
