"""LangGraph video generation workflow — full multi-agent orchestration."""

from __future__ import annotations

import time

from collections.abc import Callable
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from agents.audio_analysis_agent import AudioAnalysisAgent
from agents.avatar_agent import AvatarAgent
from agents.broll_agent import BRollAgent
from agents.image_agent import ImageAgent
from agents.storyboard_agent import StoryboardAgent
from agents.video_generation_agent import VideoGenerationAgent
from agents.director_agent import DirectorAgent
from agents.character_agent import CharacterAgent
from agents.camera_agent import CameraAgent
from agents.motion_graphics_agent import MotionGraphicsAgent
from agents.documentary_agent import DocumentaryAgent
from agents.caption_agent import CaptionAgent
from agents.country_agent import CountryAgent
from agents.cultural_adaptation_agent import CulturalAdaptationAgent
from agents.environment_agent import EnvironmentAgent
from agents.export_agent import ExportAgent
from agents.funny_moment_agent import FunnyMomentAgent
from agents.humor_localization_agent import HumorLocalizationAgent
from agents.input_agent import InputAgent
from agents.language_agent import LanguageAgent
from agents.local_video_ingest_agent import LocalVideoIngestAgent
from agents.moment_detection_agent import MomentDetectionAgent
from agents.music_agent import MusicAgent
from agents.platform_agent import PlatformAgent
from agents.quality_agent import QualityAgent
from agents.regional_agent import RegionalAgent
from agents.reframe_agent import ReframeAgent
from agents.render_agent import RenderAgent
from agents.scene_detection_agent import SceneDetectionAgent
from agents.script_agent import ScriptAgent
from agents.smart_clip_agent import SmartClipAgent
from agents.podcast_agent import PodcastAgent
from agents.research_agent import ResearchAgent
from agents.speaker_analysis_agent import SpeakerAnalysisAgent
from agents.story_agent import StoryAgent
from agents.text_agent import TextAgent
from agents.thumbnail_agent import ThumbnailAgent
from agents.seo_agent import SeoAgent
from agents.trend_agent import TrendAgent
from agents.repurpose_agent import RepurposeAgent
from agents.calendar_agent import ContentCalendarAgent
from agents.brand_agent import BrandAgent
from agents.analytics_agent import AnalyticsAgent
from agents.transcript_agent import TranscriptAgent
from agents.video_type_agent import VideoTypeAgent
from agents.visual_style_agent import VisualStyleAgent
from agents.video_understanding_agent import VideoUnderstandingAgent
from agents.viral_moment_agent import ViralMomentAgent
from agents.voice_agent import VoiceAgent
from agents.youtube_agent import YouTubeAgent
from core.errors import (
    AudioAnalysisError,
    AvatarAgentError,
    BRollAgentError,
    ImageAgentError,
    StoryboardAgentError,
    VideoGenerationAgentError,
    DirectorAgentError,
    CharacterAgentError,
    CameraAgentError,
    MotionGraphicsAgentError,
    DocumentaryAgentError,
    CaptionAgentError,
    CountryAgentError,
    CulturalAdaptationError,
    EnvironmentAgentError,
    ExportAgentError,
    FunnyMomentError,
    HumorLocalizationError,
    InputValidationError,
    LanguageAgentError,
    MomentDetectionError,
    MusicAgentError,
    PlatformAgentError,
    QualityAgentError,
    RegionalAgentError,
    ReframeAgentError,
    RenderAgentError,
    SceneDetectionError,
    ScriptAgentError,
    SmartClipError,
    PodcastAgentError,
    ResearchAgentError,
    SupervisorAgentError,
    SpeakerAnalysisError,
    StorageError,
    StoryAgentError,
    TextAgentError,
    ThumbnailAgentError,
    SeoAgentError,
    TrendAgentError,
    RepurposeAgentError,
    CalendarAgentError,
    BrandAgentError,
    AnalyticsAgentError,
    TranscriptAgentError,
    VideoTypeAgentError,
    VisualStyleAgentError,
    VideoUnderstandingError,
    ViralMomentError,
    VoiceAgentError,
    WorkflowError,
    YouTubeAgentError,
)
from core.logging import get_logger
from graph.routers import (
    route_after_avatar,
    route_after_broll,
    route_after_cultural,
    route_after_environment,
    route_after_funny,
    route_after_humor,
    route_after_image_generation,
    route_after_storyboard,
    route_after_character,
    route_after_camera,
    route_after_director,
    route_after_motion_graphics,
    route_after_documentary,
    route_after_video_generation,
    route_after_language,
    route_after_moment,
    route_after_music,
    route_after_platform,
    route_after_brand,
    route_after_seo,
    route_after_trend,
    route_after_repurpose,
    route_after_calendar,
    route_after_speaker,
    route_after_thumbnail,
    route_after_analytics,
    route_after_viral,
    route_after_voice,
    route_after_smart_clip,
    route_after_podcast,
    route_after_research,
    route_after_supervisor,
)
from graph.state_view import project_state_view
from graph.supervisor_crew import (
    run_crew_captions,
    run_crew_director,
    run_crew_research,
    run_crew_script,
    run_crew_seo,
    run_crew_story,
    run_crew_thumbnail,
    run_crew_video_generation,
    run_supervisor_turn,
)
from schemas.base import JobStatus
from schemas.job import (
    PIPELINE_STEPS,
    FeatureFlags,
    ProgressStepStatus,
    SourceType,
    VideoJobConfig,
    VideoJobRequest,
    initial_progress_steps,
)
from schemas.project import DownstreamRoute, ProjectMetadata
from tools.project.layout import ensure_project_layout, finalize_project_layout

logger = get_logger(__name__)

OnStepCallback = Callable[[dict[str, Any]], None]

INGEST_NODES: dict[str, str] = {
    DownstreamRoute.YOUTUBE_INGEST.value: "youtube_ingest",
    DownstreamRoute.LOCAL_VIDEO_INGEST.value: "local_video_ingest",
    DownstreamRoute.SCRIPT_INGEST.value: "script_ingest",
}


def _slug(label: str) -> str:
    return (
        label.lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("-", "_")
    )


# No stub pipeline steps remain (14 = Export Agent via render/quality/export)
STUB_STEP_INDICES: tuple[int, ...] = ()
STUB_NODE_NAMES: tuple[str, ...] = ()
TRANSCRIPT_NODE = f"step_02_{_slug(PIPELINE_STEPS[2])}"
UNDERSTANDING_NODE = "video_understanding"
SCENE_DETECTION_NODE = "scene_detection"
AUDIO_ANALYSIS_NODE = "audio_analysis"
SPEAKER_ANALYSIS_NODE = "speaker_analysis"
FUNNY_MOMENT_NODE = "funny_moment"
VIRAL_MOMENT_NODE = "viral_moment"
MOMENT_DETECTION_NODE = "moment_detection"
SMART_CLIP_NODE = "smart_clip"
PODCAST_NODE = "podcast"
RESEARCH_NODE = "research"
SUPERVISOR_NODE = "supervisor"
VIDEO_TYPE_NODE = "video_type"
VISUAL_STYLE_NODE = "visual_style"
ENVIRONMENT_NODE = "environment"
STORY_NODE = "story"
SCRIPT_NODE = "script"
COUNTRY_NODE = "country"
REGIONAL_NODE = "regional"
CULTURAL_NODE = "cultural"
HUMOR_NODE = "humor"
LANGUAGE_NODE = "language"
STORYBOARD_NODE = "storyboard"
CHARACTER_NODE = "character"
CAMERA_NODE = "camera"
DIRECTOR_NODE = "director"
MOTION_GRAPHICS_NODE = "motion_graphics"
DOCUMENTARY_NODE = "documentary"
VIDEO_GENERATION_NODE = "video_generation"
IMAGE_GENERATION_NODE = "image_generation"
BROLL_NODE = "b_roll"
VOICE_NODE = "voice"
AVATAR_NODE = "avatar"
MUSIC_NODE = "music"
CAPTIONS_NODE = "captions"
REFRAME_NODE = "smart_reframe"
PLATFORM_NODE = "platform"
BRAND_NODE = "brand"
SEO_NODE = "seo"
TREND_NODE = "trend"
COMPETITOR_NODE = "competitor"
REPURPOSE_NODE = "repurpose"
CALENDAR_NODE = "content_calendar"
THUMBNAIL_NODE = "thumbnail"
SHARED_AI_NODE = "shared_ai_analysis"
OBJECT_DETECTION_NODE = "object_detection"
ANALYTICS_NODE = "analytics"
RENDER_NODE = "render"
QUALITY_NODE = "quality"
EXPORT_NODE = "export"

# Backward-compatible export used by tests (PROMPT 25 order)
STEP_NODE_NAMES: tuple[str, ...] = (
    "input_agent",
    "youtube_ingest",
    "local_video_ingest",
    "script_ingest",
    TRANSCRIPT_NODE,
    UNDERSTANDING_NODE,
    SCENE_DETECTION_NODE,
    AUDIO_ANALYSIS_NODE,
    SPEAKER_ANALYSIS_NODE,
    MOMENT_DETECTION_NODE,
    FUNNY_MOMENT_NODE,
    VIRAL_MOMENT_NODE,
    SMART_CLIP_NODE,
    PODCAST_NODE,
    RESEARCH_NODE,
    SHARED_AI_NODE,
    OBJECT_DETECTION_NODE,
    SUPERVISOR_NODE,
    STORY_NODE,
    SCRIPT_NODE,
    COUNTRY_NODE,
    REGIONAL_NODE,
    LANGUAGE_NODE,
    CULTURAL_NODE,
    HUMOR_NODE,
    VIDEO_TYPE_NODE,
    VISUAL_STYLE_NODE,
    ENVIRONMENT_NODE,
    STORYBOARD_NODE,
    CHARACTER_NODE,
    CAMERA_NODE,
    DIRECTOR_NODE,
    MOTION_GRAPHICS_NODE,
    DOCUMENTARY_NODE,
    VIDEO_GENERATION_NODE,
    IMAGE_GENERATION_NODE,
    BROLL_NODE,
    VOICE_NODE,
    AVATAR_NODE,
    MUSIC_NODE,
    CAPTIONS_NODE,
    REFRAME_NODE,
    PLATFORM_NODE,
    BRAND_NODE,
    SEO_NODE,
    TREND_NODE,
    COMPETITOR_NODE,
    REPURPOSE_NODE,
    CALENDAR_NODE,
    THUMBNAIL_NODE,
    ANALYTICS_NODE,
    RENDER_NODE,
    QUALITY_NODE,
    EXPORT_NODE,
)


class WorkflowState(TypedDict):
    """LangGraph state for the video generation pipeline."""

    job: dict[str, Any]
    status: str
    current_step: int
    steps: list[dict[str, Any]]
    messages: list[str]
    error: str | None
    result: dict[str, Any] | None
    project: dict[str, Any] | None
    project_dir: str | None
    next_agent: str | None
    source_metadata: dict[str, Any] | None
    source_dir: str | None
    transcript: dict[str, Any] | None
    speech_transcript: dict[str, Any] | None
    analysis: dict[str, Any] | None
    scenes: dict[str, Any] | None
    audio_analysis: dict[str, Any] | None
    speakers: dict[str, Any] | None
    funny_moments: dict[str, Any] | None
    viral_moments: dict[str, Any] | None
    moments: dict[str, Any] | None
    clips: dict[str, Any] | None
    podcast_clips: dict[str, Any] | None
    research_report: dict[str, Any] | None
    supervisor_crew: dict[str, Any] | None
    delegation_log: list[dict[str, Any]]
    task_board: list[dict[str, Any]]
    crew_retry_counts: dict[str, int]
    crew_step: int
    video_type_pack: dict[str, Any] | None
    visual_style_pack: dict[str, Any] | None
    environment_pack: dict[str, Any] | None
    storyboard_pack: dict[str, Any] | None
    character_pack: dict[str, Any] | None
    camera_pack: dict[str, Any] | None
    director_pack: dict[str, Any] | None
    motion_graphics_pack: dict[str, Any] | None
    documentary_pack: dict[str, Any] | None
    video_generation_pack: dict[str, Any] | None
    stories: dict[str, Any] | None
    scripts: dict[str, Any] | None
    country_profile: dict[str, Any] | None
    region_profile: dict[str, Any] | None
    locale_pack: dict[str, Any] | None
    cultural_adaptation: dict[str, Any] | None
    humor_localization: dict[str, Any] | None
    localizations: dict[str, Any] | None
    image_pack: dict[str, Any] | None
    broll_pack: dict[str, Any] | None
    voice_pack: dict[str, Any] | None
    avatar_pack: dict[str, Any] | None
    music_pack: dict[str, Any] | None
    captions_pack: dict[str, Any] | None
    reframe_pack: dict[str, Any] | None
    platform_pack: dict[str, Any] | None
    brand_pack: dict[str, Any] | None
    seo_pack: dict[str, Any] | None
    trend_pack: dict[str, Any] | None
    repurpose_pack: dict[str, Any] | None
    calendar_pack: dict[str, Any] | None
    thumbnail_pack: dict[str, Any] | None
    analytics_pack: dict[str, Any] | None
    render_pack: dict[str, Any] | None
    quality_pack: dict[str, Any] | None
    export_pack: dict[str, Any] | None
    quality_retry_count: int
    # Path refs (dual-write with packs; path-only when PATH_ONLY_STATE)
    transcript_path: str | None
    analysis_path: str | None
    scenes_path: str | None
    clips_path: str | None
    research_path: str | None
    stories_path: str | None
    scripts_path: str | None
    storyboard_path: str | None
    captions_path: str | None
    platform_path: str | None
    seo_path: str | None
    trend_path: str | None
    thumbnail_path: str | None
    analytics_path: str | None
    shared_ai_analysis_path: str | None
    objects_path: str | None
    competitor_path: str | None
    competitor_pack: dict[str, Any] | None
    shared_ai_analysis: dict[str, Any] | None
    objects_pack: dict[str, Any] | None
    render_path: str | None
    export_path: str | None
    brand_path: str | None
    calendar_path: str | None
    current_pipeline: str | None
    project_refs: dict[str, Any] | None


def _mark_steps_completed(
    steps: list[dict[str, Any]],
    completed_through: int,
) -> list[dict[str, Any]]:
    """Return a copy of steps with indices <= completed_through marked completed."""
    updated = [dict(s) for s in steps]
    for i, step in enumerate(updated):
        if i <= completed_through:
            step["status"] = ProgressStepStatus.COMPLETED.value
        else:
            step["status"] = ProgressStepStatus.PENDING.value
    return updated


def _input_agent_node(state: WorkflowState) -> dict[str, Any]:
    """Real Input Agent: validate, create project, route downstream."""
    try:
        request = VideoJobRequest.model_validate(state.get("job") or {})
        result = InputAgent().run(request)
    except InputValidationError as exc:
        steps = [dict(s) for s in state.get("steps", initial_progress_steps())]
        if steps:
            steps[0]["status"] = ProgressStepStatus.FAILED.value
        messages = list(state.get("messages") or [])
        messages.append(f"[input] Validation failed: {exc}")
        return {
            "current_step": 0,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "project": None,
            "project_dir": None,
            "next_agent": None,
        }

    steps = _mark_steps_completed(
        state.get("steps", initial_progress_steps()),
        completed_through=0,
    )
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)

    return {
        **result.to_state_dict(),
        "current_step": 0,
        "steps": steps,
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _local_video_ingest_node(state: WorkflowState) -> dict[str, Any]:
    """Real local upload ingest: copy into source/, probe duration."""
    project_raw = state.get("project") or {}
    job = state.get("job") or {}
    try:
        project = ProjectMetadata.model_validate(project_raw)
        result = LocalVideoIngestAgent().run(
            project,
            project_dir=state.get("project_dir"),
            upload_path=job.get("upload_path") or project.source_path,
        )
        # Ensure layout folders early
        if state.get("project_dir"):
            ensure_project_layout(state["project_dir"])
    except (InputValidationError, StorageError) as exc:
        steps = [dict(s) for s in state.get("steps", initial_progress_steps())]
        steps = _mark_steps_completed(steps, completed_through=0)
        if len(steps) > 1:
            steps[1]["status"] = ProgressStepStatus.FAILED.value
        messages = list(state.get("messages") or [])
        messages.append(f"[local_video_ingest] Failed: {exc}")
        return {
            "current_step": 1,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "source_metadata": None,
            "source_dir": None,
        }
    except Exception as exc:  # noqa: BLE001
        steps = [dict(s) for s in state.get("steps", initial_progress_steps())]
        steps = _mark_steps_completed(steps, completed_through=0)
        if len(steps) > 1:
            steps[1]["status"] = ProgressStepStatus.FAILED.value
        messages = list(state.get("messages") or [])
        messages.append(f"[local_video_ingest] Failed: {exc}")
        return {
            "current_step": 1,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "source_metadata": None,
            "source_dir": None,
        }

    steps = _mark_steps_completed(
        state.get("steps", initial_progress_steps()),
        completed_through=1,
    )
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "current_step": 1,
        "steps": steps,
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _resolve_workflow_local_media(state: WorkflowState) -> str | None:
    """Return a resolvable local media path from project or source_metadata.

    Checks ``project.source_path`` then common metadata keys used by upload
    (``local_media_path``, ``media_path``, ``local_path``) and YouTube handoff.
    """
    from pathlib import Path

    candidates: list[str] = []
    project = state.get("project")
    if isinstance(project, dict):
        sp = project.get("source_path")
        if sp:
            candidates.append(str(sp))
    source_metadata = state.get("source_metadata")
    if isinstance(source_metadata, dict):
        for key in ("local_media_path", "media_path", "local_path"):
            value = source_metadata.get(key)
            if value:
                candidates.append(str(value))
    for path in candidates:
        if path and Path(path).is_file():
            return path
    return None


# Backward-compatible alias used by YouTube gate helpers/tests.
_youtube_local_media_path = _resolve_workflow_local_media

_NO_LOCAL_MEDIA_ERROR = (
    "No local media file available for transcription. "
    "Upload a video or provide authorized local media first."
)

_YOUTUBE_NO_MEDIA_ERROR = (
    f"{_NO_LOCAL_MEDIA_ERROR} "
    "YouTube metadata alone cannot be transcribed."
)

_LOCAL_VIDEO_NO_MEDIA_ERROR = (
    f"{_NO_LOCAL_MEDIA_ERROR} "
    "Local upload ingest did not produce a readable media file."
)


def _route_after_local_video(state: WorkflowState) -> str:
    """Continue only when a real local media file exists; else stop before Whisper."""
    if state.get("status") == JobStatus.FAILED.value or state.get("error"):
        return "local_video_failed"
    if _resolve_workflow_local_media(state) is None:
        return "local_video_failed"
    return "continue"


def _local_video_failed_node(state: WorkflowState) -> dict[str, Any]:
    """Terminal node when local video ingest fails or media is missing."""
    err = state.get("error")
    if not err and _resolve_workflow_local_media(state) is None:
        err = _LOCAL_VIDEO_NO_MEDIA_ERROR
    messages = list(state.get("messages") or [])
    if err == _LOCAL_VIDEO_NO_MEDIA_ERROR and not any(
        "No local media file" in m for m in messages
    ):
        messages.append(f"[local_video_ingest] {_LOCAL_VIDEO_NO_MEDIA_ERROR}")
    return {
        "status": JobStatus.FAILED.value,
        "error": err or "Local video ingest failed",
        "messages": messages,
    }


def _youtube_ingest_node(state: WorkflowState) -> dict[str, Any]:
    """Real YouTube Agent: metadata + source/ package (no unrestricted download)."""
    from pathlib import Path

    project_raw = state.get("project") or {}
    project_dir = state.get("project_dir")
    try:
        project = ProjectMetadata.model_validate(project_raw)
        result = YouTubeAgent().run(project, project_dir=project_dir)
    except YouTubeAgentError as exc:
        steps = [dict(s) for s in state.get("steps", initial_progress_steps())]
        steps = _mark_steps_completed(steps, completed_through=0)
        if len(steps) > 1:
            steps[1]["status"] = ProgressStepStatus.FAILED.value
        messages = list(state.get("messages") or [])
        messages.append(f"[youtube] Failed: {exc}")
        return {
            "current_step": 1,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "source_metadata": None,
            "source_dir": None,
        }

    steps = _mark_steps_completed(
        state.get("steps", initial_progress_steps()),
        completed_through=1,
    )
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    out: dict[str, Any] = {
        **result.to_state_dict(),
        "current_step": 1,
        "steps": steps,
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }
    # Persist source_path when an authorized provider supplied a real file.
    if result.local_media_path and Path(result.local_media_path).is_file():
        project_update = dict(project_raw) if isinstance(project_raw, dict) else {}
        project_update["source_path"] = str(Path(result.local_media_path).resolve())
        out["project"] = project_update
    return out


def _route_after_youtube(state: WorkflowState) -> str:
    """Continue only when a real local media file exists; else stop before Whisper."""
    if state.get("status") == JobStatus.FAILED.value or state.get("error"):
        return "youtube_failed"
    if _resolve_workflow_local_media(state) is None:
        return "youtube_failed"
    return "continue"


def _script_ingest_node(state: WorkflowState) -> dict[str, Any]:
    """Real Text Agent: structured transcript.json for script input."""
    project_raw = state.get("project") or {}
    project_dir = state.get("project_dir")
    try:
        project = ProjectMetadata.model_validate(project_raw)
        result = TextAgent().run(project, project_dir=project_dir)
    except TextAgentError as exc:
        steps = [dict(s) for s in state.get("steps", initial_progress_steps())]
        steps = _mark_steps_completed(steps, completed_through=0)
        if len(steps) > 1:
            steps[1]["status"] = ProgressStepStatus.FAILED.value
        messages = list(state.get("messages") or [])
        messages.append(f"[text] Failed: {exc}")
        return {
            "current_step": 1,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "transcript": None,
            "source_metadata": None,
            "source_dir": None,
        }

    # Script path: source detected + video/script loaded + transcript extracted
    steps = _mark_steps_completed(
        state.get("steps", initial_progress_steps()),
        completed_through=2,
    )
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "current_step": 2,
        "steps": steps,
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_script(state: WorkflowState) -> str:
    """Continue from scenes (step 3) or stop after script ingest."""
    if state.get("status") == JobStatus.FAILED.value or state.get("error"):
        return "script_failed"
    return "continue"


def _make_stub_step_node(step_index: int):
    """Create a stub node for pipeline steps 2..14."""

    label = PIPELINE_STEPS[step_index]
    node_name = f"step_{step_index:02d}_{_slug(label)}"

    def _node(state: WorkflowState) -> dict[str, Any]:
        time.sleep(0.15)
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=step_index,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"Completed: {label}")

        update: dict[str, Any] = {
            "current_step": step_index,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.RUNNING.value,
            "error": None,
        }

        if step_index == len(PIPELINE_STEPS) - 1:
            job = state.get("job") or {}
            project = state.get("project") or {}
            update["status"] = JobStatus.COMPLETED.value
            update["result"] = {
                "job_id": job.get("job_id"),
                "project_id": project.get("project_id") or job.get("job_id"),
                "source_type": job.get("source_type"),
                "project_dir": state.get("project_dir"),
                "source_dir": state.get("source_dir"),
                "source_metadata": state.get("source_metadata"),
                "transcript": state.get("transcript"),
                "speech_transcript": state.get("speech_transcript"),
                "analysis": state.get("analysis"),
                "scenes": state.get("scenes"),
                "audio_analysis": state.get("audio_analysis"),
                "speakers": state.get("speakers"),
                "moments": state.get("moments"),
                "clips": state.get("clips"),
                "video_type_pack": state.get("video_type_pack"),
                "visual_style_pack": state.get("visual_style_pack"),
                "environment_pack": state.get("environment_pack"),
                "stories": state.get("stories"),
                "scripts": state.get("scripts"),
                "localizations": state.get("localizations"),
                "cultural_adaptation": state.get("cultural_adaptation"),
                "humor_localization": state.get("humor_localization"),
                "broll_pack": state.get("broll_pack"),
                "voice_pack": state.get("voice_pack"),
                "avatar_pack": state.get("avatar_pack"),
                "music_pack": state.get("music_pack"),
                "captions_pack": state.get("captions_pack"),
                "reframe_pack": state.get("reframe_pack"),
                "platform_pack": state.get("platform_pack"),
                "brand_pack": state.get("brand_pack"),
                "seo_pack": state.get("seo_pack"),
                "trend_pack": state.get("trend_pack"),
                "repurpose_pack": state.get("repurpose_pack"),
                "calendar_pack": state.get("calendar_pack"),
                "thumbnail_pack": state.get("thumbnail_pack"),
                "analytics_pack": state.get("analytics_pack"),
                "export_path": (
                    (state.get("platform_pack") or {}).get("export_path")
                    if isinstance(state.get("platform_pack"), dict)
                    else None
                )
                or None,
                "detail": (
                    "Pipeline finished — platform metadata prepared for export; "
                    "opening platform URLs is not publishing."
                ),
            }
            logger.info(
                "Video workflow completed project_id=%s",
                project.get("project_id") or job.get("job_id"),
            )

        return update

    _node.__name__ = node_name
    return _node


def _route_after_input(state: WorkflowState) -> str:
    """Conditional edge target after the Input Agent."""
    if state.get("status") == JobStatus.FAILED.value or state.get("error"):
        return "input_failed"
    next_agent = state.get("next_agent") or ""
    if next_agent in INGEST_NODES:
        return INGEST_NODES[next_agent]
    # Fallback from source_type on project/job
    project = state.get("project") or {}
    source = project.get("source_type") or (state.get("job") or {}).get("source_type")
    if source == SourceType.YOUTUBE.value:
        return "youtube_ingest"
    if source == SourceType.UPLOAD.value:
        return "local_video_ingest"
    if source == SourceType.SCRIPT.value:
        return "script_ingest"
    return "input_failed"


def _input_failed_node(state: WorkflowState) -> dict[str, Any]:
    """Terminal node when Input Agent validation fails."""
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Input validation failed",
    }


def _youtube_failed_node(state: WorkflowState) -> dict[str, Any]:
    """Terminal node when YouTube Agent fails or local media is missing."""
    err = state.get("error")
    if not err and _youtube_local_media_path(state) is None:
        err = _YOUTUBE_NO_MEDIA_ERROR
    messages = list(state.get("messages") or [])
    if err and not any("No local media file" in m for m in messages):
        if err == _YOUTUBE_NO_MEDIA_ERROR:
            messages.append(f"[youtube] {_YOUTUBE_NO_MEDIA_ERROR}")
    return {
        "status": JobStatus.FAILED.value,
        "error": err or "YouTube ingest failed",
        "messages": messages,
    }


def _script_failed_node(state: WorkflowState) -> dict[str, Any]:
    """Terminal node when Text Agent fails."""
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Script ingest failed",
    }


def _transcript_extract_node(state: WorkflowState) -> dict[str, Any]:
    """Real Transcript Agent: local Whisper speech-to-text."""
    project_raw = state.get("project") or {}
    project_dir = state.get("project_dir")
    source_metadata = state.get("source_metadata")
    try:
        project = ProjectMetadata.model_validate(project_raw)
        result = TranscriptAgent().run(
            project,
            project_dir=project_dir,
            source_metadata=source_metadata,
        )
    except TranscriptAgentError as exc:
        steps = [dict(s) for s in state.get("steps", initial_progress_steps())]
        steps = _mark_steps_completed(steps, completed_through=1)
        if len(steps) > 2:
            steps[2]["status"] = ProgressStepStatus.FAILED.value
        messages = list(state.get("messages") or [])
        messages.append(f"[transcript] Failed: {exc}")
        return {
            "current_step": 2,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "transcript": None,
            "speech_transcript": None,
        }

    steps = _mark_steps_completed(
        state.get("steps", initial_progress_steps()),
        completed_through=2,
    )
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "current_step": 2,
        "steps": steps,
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_transcript(state: WorkflowState) -> str:
    if state.get("status") == JobStatus.FAILED.value or state.get("error"):
        return "transcript_failed"
    return "continue"


def _transcript_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Transcript extraction failed",
    }


def _video_understanding_node(state: WorkflowState) -> dict[str, Any]:
    """Real Video Understanding Agent: scenes + audio analysis."""
    project_raw = state.get("project") or {}
    try:
        project = ProjectMetadata.model_validate(project_raw)
        result = VideoUnderstandingAgent().run(
            project,
            project_dir=state.get("project_dir"),
            source_metadata=state.get("source_metadata"),
            speech_transcript=state.get("speech_transcript"),
            transcript=state.get("transcript"),
        )
    except VideoUnderstandingError as exc:
        steps = [dict(s) for s in state.get("steps", initial_progress_steps())]
        steps = _mark_steps_completed(steps, completed_through=2)
        if len(steps) > 3:
            steps[3]["status"] = ProgressStepStatus.FAILED.value
        messages = list(state.get("messages") or [])
        messages.append(f"[video_understanding] Failed: {exc}")
        return {
            "current_step": 3,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "analysis": None,
        }

    steps = _mark_steps_completed(
        state.get("steps", initial_progress_steps()),
        completed_through=4,
    )
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "current_step": 4,
        "steps": steps,
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_understanding(state: WorkflowState) -> str:
    if state.get("status") == JobStatus.FAILED.value or state.get("error"):
        return "understanding_failed"
    return "continue"


def _understanding_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Video understanding failed",
    }


def _scene_detection_node(state: WorkflowState) -> dict[str, Any]:
    """Real Scene Detection Agent: write analysis/scenes.json (signals only)."""
    project_raw = state.get("project") or {}
    try:
        project = ProjectMetadata.model_validate(project_raw)
        result = SceneDetectionAgent().run(
            project,
            project_dir=state.get("project_dir"),
            source_metadata=state.get("source_metadata"),
            analysis=state.get("analysis"),
            speech_transcript=state.get("speech_transcript"),
            transcript=state.get("transcript"),
        )
    except SceneDetectionError as exc:
        steps = [dict(s) for s in state.get("steps", initial_progress_steps())]
        steps = _mark_steps_completed(steps, completed_through=4)
        messages = list(state.get("messages") or [])
        messages.append(f"[scene_detection] Failed: {exc}")
        return {
            "current_step": 4,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "scenes": None,
        }

    steps = _mark_steps_completed(
        state.get("steps", initial_progress_steps()),
        completed_through=4,
    )
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "current_step": 4,
        "steps": steps,
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_scene_detection(state: WorkflowState) -> str:
    if state.get("status") == JobStatus.FAILED.value or state.get("error"):
        return "scene_detection_failed"
    return "continue"


def _scene_detection_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Scene detection failed",
    }


def _audio_analysis_node(state: WorkflowState) -> dict[str, Any]:
    """Real Audio Analysis Agent: write analysis/audio_analysis.json."""
    project_raw = state.get("project") or {}
    try:
        project = ProjectMetadata.model_validate(project_raw)
        result = AudioAnalysisAgent().run(
            project,
            project_dir=state.get("project_dir"),
            source_metadata=state.get("source_metadata"),
            analysis=state.get("analysis"),
            speech_transcript=state.get("speech_transcript"),
            transcript=state.get("transcript"),
        )
    except AudioAnalysisError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=4,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[audio_analysis] Failed: {exc}")
        return {
            "current_step": 4,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "audio_analysis": None,
        }

    steps = _mark_steps_completed(
        state.get("steps", initial_progress_steps()),
        completed_through=4,
    )
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "current_step": 4,
        "steps": steps,
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_audio_analysis(state: WorkflowState) -> str:
    if state.get("status") == JobStatus.FAILED.value or state.get("error"):
        return "audio_analysis_failed"
    return "continue"


def _audio_analysis_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Audio analysis failed",
    }


def _speaker_analysis_node(state: WorkflowState) -> dict[str, Any]:
    """Real Speaker Analysis Agent: write analysis/speakers.json."""
    project_raw = state.get("project") or {}
    try:
        project = ProjectMetadata.model_validate(project_raw)
        result = SpeakerAnalysisAgent().run(
            project,
            project_dir=state.get("project_dir"),
            source_metadata=state.get("source_metadata"),
            analysis=state.get("analysis"),
            speech_transcript=state.get("speech_transcript"),
            transcript=state.get("transcript"),
            audio_analysis=state.get("audio_analysis"),
            scenes=state.get("scenes"),
        )
    except SpeakerAnalysisError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=4,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[speaker_analysis] Failed: {exc}")
        return {
            "current_step": 4,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "speakers": None,
        }

    steps = _mark_steps_completed(
        state.get("steps", initial_progress_steps()),
        completed_through=4,
    )
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "current_step": 4,
        "steps": steps,
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_speaker_analysis(state: WorkflowState) -> str:
    return route_after_speaker(state)


def _speaker_analysis_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Speaker analysis failed",
    }


def _moment_detection_node(state: WorkflowState) -> dict[str, Any]:
    """Moment Detection Agent: write analysis/moments.json (step 5)."""
    project_raw = state.get("project") or {}
    job = state.get("job") or {}
    try:
        project = ProjectMetadata.model_validate(project_raw)
        result = MomentDetectionAgent().run(
            project,
            project_dir=state.get("project_dir"),
            features=job.get("features"),
            transcript=state.get("transcript"),
            speech_transcript=state.get("speech_transcript"),
            scenes=state.get("scenes"),
            audio_analysis=state.get("audio_analysis"),
            speakers=state.get("speakers"),
            analysis=state.get("analysis"),
            funny_moments=state.get("funny_moments"),
            viral_moments=state.get("viral_moments"),
        )
    except MomentDetectionError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=4,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[moment_detection] Failed: {exc}")
        return {
            "current_step": 5,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "moments": None,
        }

    steps = _mark_steps_completed(
        state.get("steps", initial_progress_steps()),
        completed_through=5,
    )
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "current_step": 5,
        "steps": steps,
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_moment_detection(state: WorkflowState) -> str:
    return route_after_moment(state)


def _moment_detection_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Moment detection failed",
    }


def _funny_moment_node(state: WorkflowState) -> dict[str, Any]:
    """Funny Moment Agent: write analysis/funny_moments.json (step 6)."""
    project_raw = state.get("project") or {}
    job = state.get("job") or {}
    try:
        project = ProjectMetadata.model_validate(project_raw)
        result = FunnyMomentAgent().run(
            project,
            project_dir=state.get("project_dir"),
            features=job.get("features"),
            transcript=state.get("transcript"),
            speech_transcript=state.get("speech_transcript"),
            scenes=state.get("scenes"),
            audio_analysis=state.get("audio_analysis"),
            speakers=state.get("speakers"),
            analysis=state.get("analysis"),
        )
    except FunnyMomentError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=5,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[funny_moment] Failed: {exc}")
        return {
            "current_step": 6,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "funny_moments": None,
        }

    steps = _mark_steps_completed(
        state.get("steps", initial_progress_steps()),
        completed_through=6,
    )
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "current_step": 6,
        "steps": steps,
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_funny_moment(state: WorkflowState) -> str:
    return route_after_funny(state)


def _funny_moment_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Funny moment detection failed",
    }


def _skip_funny_node(state: WorkflowState) -> dict[str, Any]:
    """Graph-level skip: write disabled funny pack without Gemini."""
    project_raw = state.get("project") or {}
    features = dict((state.get("job") or {}).get("features") or {})
    features["funny_moments"] = False
    project = ProjectMetadata.model_validate(project_raw)
    result = FunnyMomentAgent().run(
        project,
        project_dir=state.get("project_dir"),
        features=features,
        transcript=state.get("transcript"),
        speech_transcript=state.get("speech_transcript"),
        scenes=state.get("scenes"),
        audio_analysis=state.get("audio_analysis"),
        speakers=state.get("speakers"),
        analysis=state.get("analysis"),
    )
    messages = list(state.get("messages") or [])
    messages.append("[funny_moment] Skipped (feature off)")
    messages.extend(result.messages)
    steps = _mark_steps_completed(
        state.get("steps", initial_progress_steps()),
        completed_through=6,
    )
    return {
        **result.to_state_dict(),
        "current_step": 6,
        "steps": steps,
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _viral_moment_node(state: WorkflowState) -> dict[str, Any]:
    """Viral Moment Agent: write analysis/viral_moments.json (step 7)."""
    project_raw = state.get("project") or {}
    job = state.get("job") or {}
    try:
        project = ProjectMetadata.model_validate(project_raw)
        result = ViralMomentAgent().run(
            project,
            project_dir=state.get("project_dir"),
            features=job.get("features"),
            transcript=state.get("transcript"),
            speech_transcript=state.get("speech_transcript"),
            scenes=state.get("scenes"),
            audio_analysis=state.get("audio_analysis"),
            speakers=state.get("speakers"),
            analysis=state.get("analysis"),
            funny_moments=state.get("funny_moments"),
        )
    except ViralMomentError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=6,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[viral_moment] Failed: {exc}")
        return {
            "current_step": 7,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "viral_moments": None,
        }

    steps = _mark_steps_completed(
        state.get("steps", initial_progress_steps()),
        completed_through=7,
    )
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "current_step": 7,
        "steps": steps,
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_viral_moment(state: WorkflowState) -> str:
    return route_after_viral(state)


def _viral_moment_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Viral moment detection failed",
    }


def _skip_viral_node(state: WorkflowState) -> dict[str, Any]:
    project_raw = state.get("project") or {}
    features = dict((state.get("job") or {}).get("features") or {})
    features["viral_moments"] = False
    project = ProjectMetadata.model_validate(project_raw)
    result = ViralMomentAgent().run(
        project,
        project_dir=state.get("project_dir"),
        features=features,
        transcript=state.get("transcript"),
        speech_transcript=state.get("speech_transcript"),
        scenes=state.get("scenes"),
        audio_analysis=state.get("audio_analysis"),
        speakers=state.get("speakers"),
        analysis=state.get("analysis"),
        funny_moments=state.get("funny_moments"),
    )
    messages = list(state.get("messages") or [])
    messages.append("[viral_moment] Skipped (feature off)")
    messages.extend(result.messages)
    steps = _mark_steps_completed(
        state.get("steps", initial_progress_steps()),
        completed_through=7,
    )
    return {
        **result.to_state_dict(),
        "current_step": 7,
        "steps": steps,
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }

def _smart_clip_node(state: WorkflowState) -> dict[str, Any]:
    """Smart Clip Agent: write analysis/clips.json (pipeline step 8)."""
    project_raw = state.get("project") or {}
    job = state.get("job") or {}
    try:
        project = ProjectMetadata.model_validate(project_raw)
        result = SmartClipAgent().run(
            project,
            project_dir=state.get("project_dir"),
            features=job.get("features"),
            config=job.get("config"),
            transcript=state.get("transcript"),
            speech_transcript=state.get("speech_transcript"),
            scenes=state.get("scenes"),
            audio_analysis=state.get("audio_analysis"),
            speakers=state.get("speakers"),
            moments=state.get("moments"),
            funny_moments=state.get("funny_moments"),
            viral_moments=state.get("viral_moments"),
            analysis=state.get("analysis"),
            documentary_pack=state.get("documentary_pack"),
            director_pack=state.get("director_pack"),
        )
    except SmartClipError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=7,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[smart_clip] Failed: {exc}")
        return {
            "current_step": 8,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "clips": None,
        }

    steps = _mark_steps_completed(
        state.get("steps", initial_progress_steps()),
        completed_through=8,
    )
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "current_step": 8,
        "steps": steps,
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_smart_clip(state: WorkflowState) -> str:
    return route_after_smart_clip(state)


def _smart_clip_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Smart clip selection failed",
    }


def _skip_podcast_node(state: WorkflowState) -> dict[str, Any]:
    project_raw = state.get("project") or {}
    features = dict((state.get("job") or {}).get("features") or {})
    features["podcast_clips"] = False
    job = state.get("job") or {}
    config = dict(job.get("config") or {})
    # Force non-podcast type so agent soft-skips when flag off
    if str(config.get("video_type") or "").lower() in {"podcast", "interview"}:
        config = {**config, "video_type": "Shorts"}
    project = ProjectMetadata.model_validate(project_raw)
    result = PodcastAgent().run(
        project,
        project_dir=state.get("project_dir"),
        features=features,
        config=config,
        transcript=state.get("transcript"),
        speech_transcript=state.get("speech_transcript"),
        scenes=state.get("scenes"),
        audio_analysis=state.get("audio_analysis"),
        speakers=state.get("speakers"),
        moments=state.get("moments"),
        funny_moments=state.get("funny_moments"),
        viral_moments=state.get("viral_moments"),
        clips=state.get("clips"),
        analysis=state.get("analysis"),
        source_metadata=state.get("source_metadata"),
        upload_path=job.get("upload_path") or (project_raw.get("source_path") if isinstance(project_raw, dict) else None),
    )
    messages = list(state.get("messages") or [])
    messages.append("[podcast] Skipped (feature/video_type off)")
    messages.extend(result.messages)
    steps = _mark_steps_completed(
        state.get("steps", initial_progress_steps()),
        completed_through=8,
    )
    return {
        **result.to_state_dict(),
        "current_step": 8,
        "steps": steps,
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _podcast_node(state: WorkflowState) -> dict[str, Any]:
    """Podcast Agent: write analysis/podcast_clips.json (under clips milestone)."""
    project_raw = state.get("project") or {}
    job = state.get("job") or {}
    try:
        project = ProjectMetadata.model_validate(project_raw)
        result = PodcastAgent().run(
            project,
            project_dir=state.get("project_dir"),
            features=job.get("features"),
            config=job.get("config"),
            transcript=state.get("transcript"),
            speech_transcript=state.get("speech_transcript"),
            scenes=state.get("scenes"),
            audio_analysis=state.get("audio_analysis"),
            speakers=state.get("speakers"),
            moments=state.get("moments"),
            funny_moments=state.get("funny_moments"),
            viral_moments=state.get("viral_moments"),
            clips=state.get("clips"),
            analysis=state.get("analysis"),
            source_metadata=state.get("source_metadata"),
            upload_path=job.get("upload_path")
            or (
                project_raw.get("source_path")
                if isinstance(project_raw, dict)
                else None
            ),
        )
    except PodcastAgentError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=8,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[podcast] Failed: {exc}")
        return {
            "current_step": 8,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "podcast_clips": None,
        }

    steps = _mark_steps_completed(
        state.get("steps", initial_progress_steps()),
        completed_through=8,
    )
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "current_step": 8,
        "steps": steps,
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_podcast(state: WorkflowState) -> str:
    return route_after_podcast(state)


def _podcast_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Podcast packaging failed",
    }


def _skip_research_node(state: WorkflowState) -> dict[str, Any]:
    project_raw = state.get("project") or {}
    features = dict((state.get("job") or {}).get("features") or {})
    features["research"] = False
    job = state.get("job") or {}
    # Force non-SCRIPT source_type so agent soft-skips when flag off
    project = ProjectMetadata.model_validate(project_raw)
    forced_project = project.model_copy(
        update={"source_type": SourceType.UPLOAD}
        if project.source_type == SourceType.SCRIPT
        else {}
    )
    result = ResearchAgent().run(
        forced_project,
        project_dir=state.get("project_dir"),
        features=features,
        config=job.get("config"),
        transcript=state.get("transcript"),
        speech_transcript=state.get("speech_transcript"),
        analysis=state.get("analysis"),
        source_metadata=state.get("source_metadata"),
        source_type=SourceType.UPLOAD,
        youtube_url=job.get("youtube_url") or getattr(project, "youtube_url", None),
    )
    messages = list(state.get("messages") or [])
    messages.append("[research] Skipped (feature/source_type off)")
    messages.extend(result.messages)
    steps = _mark_steps_completed(
        state.get("steps", initial_progress_steps()),
        completed_through=8,
    )
    return {
        **result.to_state_dict(),
        "current_step": 8,
        "steps": steps,
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _research_node(state: WorkflowState) -> dict[str, Any]:
    """Research Agent: write analysis/research_report.json (before story)."""
    project_raw = state.get("project") or {}
    job = state.get("job") or {}
    try:
        project = ProjectMetadata.model_validate(project_raw)
        result = ResearchAgent().run(
            project,
            project_dir=state.get("project_dir"),
            features=job.get("features"),
            config=job.get("config"),
            transcript=state.get("transcript"),
            speech_transcript=state.get("speech_transcript"),
            analysis=state.get("analysis"),
            source_metadata=state.get("source_metadata"),
            source_type=job.get("source_type") or project.source_type,
            youtube_url=job.get("youtube_url") or getattr(project, "youtube_url", None),
        )
    except ResearchAgentError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=8,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[research] Failed: {exc}")
        return {
            "current_step": 8,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "research_report": None,
        }

    steps = _mark_steps_completed(
        state.get("steps", initial_progress_steps()),
        completed_through=8,
    )
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "current_step": 8,
        "steps": steps,
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_research(state: WorkflowState) -> str:
    return route_after_research(state)


def _research_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Research report failed",
    }


def _shared_ai_analysis_node(state: WorkflowState) -> dict[str, Any]:
    """Write analysis/shared_ai_analysis.json once for downstream agents."""
    messages = list(state.get("messages") or [])
    project_dir = state.get("project_dir")
    if not project_dir:
        messages.append("[shared_ai] Soft-skip — no project_dir")
        return {"messages": messages, "shared_ai_analysis": None}
    try:
        from tools.analysis.shared_ai import build_shared_ai_analysis
        from schemas.project_refs import dual_write_paths

        analyze_fn = None
        # Gemini enrich is optional; heuristic report always written.

        report = build_shared_ai_analysis(
            project_dir=project_dir,
            transcript=state.get("speech_transcript") or state.get("transcript"),
            job=state.get("job") if isinstance(state.get("job"), dict) else None,
            analysis=state.get("analysis") if isinstance(state.get("analysis"), dict) else None,
            analyze_fn=analyze_fn,
        )
        path = str(report.get("path") or "")
        messages.append(f"[shared_ai] Wrote shared_ai_analysis.json source={report.get('source')}")
        update = {
            "messages": messages,
            "shared_ai_analysis": report,
            "shared_ai_analysis_path": path,
            "status": JobStatus.RUNNING.value,
            "error": None,
        }
        return dual_write_paths(
            update,
            project_dir=str(project_dir),
            written_paths={"shared_ai_analysis_path": path} if path else None,
        )
    except Exception as exc:  # noqa: BLE001
        messages.append(f"[shared_ai] Soft-failed: {exc}")
        return {"messages": messages}


def _object_detection_node(state: WorkflowState) -> dict[str, Any]:
    """Keyframe object cues → analysis/objects.json (soft-skip friendly)."""
    messages = list(state.get("messages") or [])
    project_dir = state.get("project_dir")
    try:
        from config.settings import get_settings
        from tools.vision.objects import detect_objects_at_keyframes, write_objects_json
        from schemas.project_refs import dual_write_paths

        enabled = bool(get_settings().object_detection)
        media = None
        meta = state.get("source_metadata") or {}
        if isinstance(meta, dict):
            media = meta.get("local_path") or meta.get("path")
        project = state.get("project") or {}
        if not media and isinstance(project, dict):
            media = project.get("source_path") or project.get("video_path")

        payload = detect_objects_at_keyframes(
            media,
            scenes=state.get("scenes") if isinstance(state.get("scenes"), dict) else None,
            clips=state.get("clips") if isinstance(state.get("clips"), dict) else None,
            enabled=enabled,
        )
        path = ""
        if project_dir:
            path = write_objects_json(project_dir, payload)
        messages.append(
            f"[objects] skipped={payload.get('skipped')} count={len(payload.get('objects') or [])}"
        )
        update = {
            "messages": messages,
            "objects_pack": payload,
            "objects_path": path or None,
            "status": JobStatus.RUNNING.value,
            "error": None,
        }
        return dual_write_paths(
            update,
            project_dir=str(project_dir) if project_dir else None,
            written_paths={"objects_path": path} if path else None,
        )
    except Exception as exc:  # noqa: BLE001
        messages.append(f"[objects] Soft-failed: {exc}")
        return {"messages": messages}


def _competitor_node(state: WorkflowState) -> dict[str, Any]:
    """Growth competitor scaffold with 7d cache."""
    messages = list(state.get("messages") or [])
    project_dir = state.get("project_dir")
    try:
        from tools.cache.competitors import get_or_build_competitor_pack
        from schemas.project_refs import dual_write_paths
        import json
        from pathlib import Path

        topics: list[str] = []
        shared = state.get("shared_ai_analysis")
        if isinstance(shared, dict):
            topics = [str(t) for t in (shared.get("topics") or []) if t][:6]
        trend = state.get("trend_pack")
        if isinstance(trend, dict):
            plan = trend.get("plan") or {}
            if isinstance(plan, dict):
                topics.extend(str(t) for t in (plan.get("trend_topics") or []) if t)

        job = state.get("job") or {}
        platform = "YouTube"
        niche = ""
        if isinstance(job, dict):
            cfg = job.get("config") or {}
            if isinstance(cfg, dict):
                platform = str(cfg.get("platform") or platform)
                niche = str(cfg.get("topic") or cfg.get("audience") or "")

        pack = get_or_build_competitor_pack(
            niche=niche,
            platform=platform,
            topics=topics,
        )
        path = ""
        if project_dir:
            out = Path(project_dir) / "analysis" / "competitor_pack.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(pack, indent=2), encoding="utf-8")
            path = str(out)
        messages.append(
            f"[competitor] cache_hit={pack.get('cache_hit')} peers={len(pack.get('competitors') or [])}"
        )
        update = {
            "messages": messages,
            "competitor_pack": pack,
            "competitor_path": path or None,
            "status": JobStatus.RUNNING.value,
            "error": None,
        }
        return dual_write_paths(
            update,
            project_dir=str(project_dir) if project_dir else None,
            written_paths={"competitor_path": path} if path else None,
        )
    except Exception as exc:  # noqa: BLE001
        messages.append(f"[competitor] Soft-failed: {exc}")
        return {"messages": messages}


def _route_after_shared_ai(state: WorkflowState) -> str:
    return _route_after_research(state)


def _route_after_objects(state: WorkflowState) -> str:
    return _route_after_research(state)


def _route_after_competitor(state: WorkflowState) -> str:
    return _route_after_trend(state)


def _supervisor_node(state: WorkflowState) -> dict[str, Any]:
    """Supervisor: delegate next crew worker or FINISH."""
    return run_supervisor_turn(state)


def _route_after_supervisor(state: WorkflowState) -> str:
    return route_after_supervisor(state)


def _crew_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Supervisor crew failed",
    }


def _crew_worker_research_node(state: WorkflowState) -> dict[str, Any]:
    return run_crew_research(state)


def _crew_worker_story_node(state: WorkflowState) -> dict[str, Any]:
    return run_crew_story(state)


def _crew_worker_script_node(state: WorkflowState) -> dict[str, Any]:
    return run_crew_script(state)


def _crew_worker_director_node(state: WorkflowState) -> dict[str, Any]:
    return run_crew_director(state)


def _crew_worker_video_generation_node(state: WorkflowState) -> dict[str, Any]:
    return run_crew_video_generation(state)


def _crew_worker_captions_node(state: WorkflowState) -> dict[str, Any]:
    return run_crew_captions(state)


def _crew_worker_thumbnail_node(state: WorkflowState) -> dict[str, Any]:
    return run_crew_thumbnail(state)


def _crew_worker_seo_node(state: WorkflowState) -> dict[str, Any]:
    return run_crew_seo(state)


def _video_type_node(state: WorkflowState) -> dict[str, Any]:
    """Video Type Agent: resolve preset → analysis/video_type.json (under step 9)."""
    project = state.get("project")
    if not project:
        return {
            "status": JobStatus.FAILED.value,
            "error": "Missing project for video type resolution",
            "video_type_pack": None,
        }

    job = state.get("job") or {}
    try:
        result = VideoTypeAgent().run(
            project,
            project_dir=state.get("project_dir"),
            config=job.get("config"),
        )
    except VideoTypeAgentError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=10,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[video_type] Failed: {exc}")
        return {
            "current_step": 9,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "video_type_pack": None,
        }

    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "current_step": 10,
        "steps": _step11_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_video_type(state: WorkflowState) -> str:
    if state.get("status") == JobStatus.FAILED.value or state.get("error"):
        return "video_type_failed"
    return "continue"


def _video_type_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Video type resolution failed",
    }


def _visual_style_node(state: WorkflowState) -> dict[str, Any]:
    """Visual Style Agent: resolve plan → analysis/visual_style.json (under step 9)."""
    project = state.get("project")
    if not project:
        return {
            "status": JobStatus.FAILED.value,
            "error": "Missing project for visual style resolution",
            "visual_style_pack": None,
        }

    job = state.get("job") or {}
    try:
        result = VisualStyleAgent().run(
            project,
            project_dir=state.get("project_dir"),
            config=job.get("config"),
        )
    except VisualStyleAgentError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=10,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[visual_style] Failed: {exc}")
        return {
            "current_step": 9,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "visual_style_pack": None,
        }

    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "current_step": 10,
        "steps": _step11_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_visual_style(state: WorkflowState) -> str:
    if state.get("status") == JobStatus.FAILED.value or state.get("error"):
        return "visual_style_failed"
    return "continue"


def _visual_style_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Visual style resolution failed",
    }


def _environment_node(state: WorkflowState) -> dict[str, Any]:
    """Environment Agent: resolve plan → analysis/environment.json (under step 9)."""
    project = state.get("project")
    if not project:
        return {
            "status": JobStatus.FAILED.value,
            "error": "Missing project for environment resolution",
            "environment_pack": None,
        }

    job = state.get("job") or {}
    try:
        result = EnvironmentAgent().run(
            project,
            project_dir=state.get("project_dir"),
            config=job.get("config"),
        )
    except EnvironmentAgentError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=10,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[environment] Failed: {exc}")
        return {
            "current_step": 9,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "environment_pack": None,
        }

    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "current_step": 10,
        "steps": _step11_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_environment(state: WorkflowState) -> str:
    return route_after_environment(state)


def _environment_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Environment resolution failed",
    }


def _story_node(state: WorkflowState) -> dict[str, Any]:
    """Story Agent: write analysis/stories.json (part of pipeline step 9)."""
    project = state.get("project")
    if not project:
        return {
            "status": JobStatus.FAILED.value,
            "error": "Missing project for story generation",
            "stories": None,
        }

    job = state.get("job") or {}
    try:
        result = StoryAgent().run(
            project,
            project_dir=state.get("project_dir"),
            clips=state.get("clips"),
            transcript=state.get("transcript"),
            speech_transcript=state.get("speech_transcript"),
            config=job.get("config"),
            video_type_pack=state.get("video_type_pack"),
            visual_style_pack=state.get("visual_style_pack"),
            environment_pack=state.get("environment_pack"),
            research_report=state.get("research_report"),
        )
    except StoryAgentError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=8,
        )
        if len(steps) > 9:
            steps[9]["status"] = ProgressStepStatus.FAILED.value
        messages = list(state.get("messages") or [])
        messages.append(f"[story] Failed: {exc}")
        return {
            "current_step": 9,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "stories": None,
        }

    # Step 9 completes after Script Agent; keep story step running visually.
    steps = list(state.get("steps") or initial_progress_steps())
    steps = [dict(s) for s in steps]
    for i, step in enumerate(steps):
        if i <= 8:
            step["status"] = ProgressStepStatus.COMPLETED.value
        elif i == 9:
            step["status"] = ProgressStepStatus.RUNNING.value
        else:
            step["status"] = ProgressStepStatus.PENDING.value
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "current_step": 8,
        "steps": steps,
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_story(state: WorkflowState) -> str:
    if state.get("status") == JobStatus.FAILED.value or state.get("error"):
        return "story_failed"
    return "continue"


def _story_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Story generation failed",
    }


def _script_node(state: WorkflowState) -> dict[str, Any]:
    """Script Agent: write analysis/scripts.json (completes pipeline step 9)."""
    project = state.get("project")
    if not project:
        return {
            "status": JobStatus.FAILED.value,
            "error": "Missing project for script generation",
            "scripts": None,
        }

    job = state.get("job") or {}
    try:
        result = ScriptAgent().run(
            project,
            project_dir=state.get("project_dir"),
            clips=state.get("clips"),
            stories=state.get("stories"),
            transcript=state.get("transcript"),
            speech_transcript=state.get("speech_transcript"),
            config=job.get("config"),
            video_type_pack=state.get("video_type_pack"),
            visual_style_pack=state.get("visual_style_pack"),
            environment_pack=state.get("environment_pack"),
            research_report=state.get("research_report"),
        )
    except ScriptAgentError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=8,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[script] Failed: {exc}")
        return {
            "current_step": 9,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "scripts": None,
        }

    steps = _mark_steps_completed(
        state.get("steps", initial_progress_steps()),
        completed_through=9,
    )
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "current_step": 9,
        "steps": steps,
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_script_gen(state: WorkflowState) -> str:
    if state.get("status") == JobStatus.FAILED.value or state.get("error"):
        return "script_gen_failed"
    return "continue"


def _script_gen_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Script generation failed",
    }


def _mark_localization_running(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    updated = [dict(s) for s in steps]
    for i, step in enumerate(updated):
        if i <= 9:
            step["status"] = ProgressStepStatus.COMPLETED.value
        elif i == 10:
            step["status"] = ProgressStepStatus.RUNNING.value
        else:
            step["status"] = ProgressStepStatus.PENDING.value
    return updated


def _country_node(state: WorkflowState) -> dict[str, Any]:
    """Country Agent: resolve country profile (part of step 10)."""
    project = state.get("project")
    if not project:
        return {
            "status": JobStatus.FAILED.value,
            "error": "Missing project for country localization",
            "country_profile": None,
        }

    job = state.get("job") or {}
    try:
        result = CountryAgent().run(
            project,
            project_dir=state.get("project_dir"),
            config=job.get("config"),
            features=job.get("features"),
        )
    except CountryAgentError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=9,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[country] Failed: {exc}")
        return {
            "current_step": 10,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "country_profile": None,
        }

    steps = _mark_localization_running(
        state.get("steps", initial_progress_steps())
    )
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "current_step": 9,
        "steps": steps,
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_country(state: WorkflowState) -> str:
    if state.get("status") == JobStatus.FAILED.value or state.get("error"):
        return "country_failed"
    return "continue"


def _country_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Country localization failed",
    }


def _regional_node(state: WorkflowState) -> dict[str, Any]:
    """Regional Agent: resolve region profile (part of step 10)."""
    project = state.get("project")
    if not project:
        return {
            "status": JobStatus.FAILED.value,
            "error": "Missing project for regional localization",
            "region_profile": None,
        }

    job = state.get("job") or {}
    try:
        result = RegionalAgent().run(
            project,
            project_dir=state.get("project_dir"),
            config=job.get("config"),
            features=job.get("features"),
            country_profile=state.get("country_profile"),
        )
    except RegionalAgentError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=9,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[regional] Failed: {exc}")
        return {
            "current_step": 10,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "region_profile": None,
        }

    steps = _mark_localization_running(
        state.get("steps", initial_progress_steps())
    )
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "current_step": 9,
        "steps": steps,
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_regional(state: WorkflowState) -> str:
    if state.get("status") == JobStatus.FAILED.value or state.get("error"):
        return "regional_failed"
    return "language"


def _regional_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Regional localization failed",
    }


def _cultural_node(state: WorkflowState) -> dict[str, Any]:
    """Cultural Adaptation Agent (part of step 10)."""
    project = state.get("project")
    if not project:
        return {
            "status": JobStatus.FAILED.value,
            "error": "Missing project for cultural adaptation",
            "cultural_adaptation": None,
        }

    job = state.get("job") or {}
    try:
        result = CulturalAdaptationAgent().run(
            project,
            project_dir=state.get("project_dir"),
            config=job.get("config"),
            features=job.get("features"),
            scripts=state.get("scripts"),
            locale_pack=state.get("locale_pack"),
        )
    except CulturalAdaptationError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=9,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[cultural] Failed: {exc}")
        return {
            "current_step": 10,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "cultural_adaptation": None,
        }

    steps = _mark_localization_running(
        state.get("steps", initial_progress_steps())
    )
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "current_step": 9,
        "steps": steps,
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_cultural(state: WorkflowState) -> str:
    return route_after_cultural(state)


def _cultural_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Cultural adaptation failed",
    }


def _humor_node(state: WorkflowState) -> dict[str, Any]:
    """Humor Localization Agent (part of step 10)."""
    project = state.get("project")
    if not project:
        return {
            "status": JobStatus.FAILED.value,
            "error": "Missing project for humor localization",
            "humor_localization": None,
        }

    job = state.get("job") or {}
    try:
        result = HumorLocalizationAgent().run(
            project,
            project_dir=state.get("project_dir"),
            config=job.get("config"),
            features=job.get("features"),
            scripts=state.get("scripts"),
            locale_pack=state.get("locale_pack"),
            cultural_adaptation=state.get("cultural_adaptation"),
        )
    except HumorLocalizationError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=9,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[humor] Failed: {exc}")
        return {
            "current_step": 10,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "humor_localization": None,
        }

    steps = _mark_steps_completed(
        state.get("steps", initial_progress_steps()),
        completed_through=10,
    )
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "current_step": 10,
        "steps": steps,
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_humor(state: WorkflowState) -> str:
    return route_after_humor(state)


def _humor_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Humor localization failed",
    }


def _language_node(state: WorkflowState) -> dict[str, Any]:
    """Language Agent: write analysis/localizations.json (part of step 10)."""
    project = state.get("project")
    if not project:
        return {
            "status": JobStatus.FAILED.value,
            "error": "Missing project for language localization",
            "localizations": None,
        }

    job = state.get("job") or {}
    try:
        result = LanguageAgent().run(
            project,
            project_dir=state.get("project_dir"),
            config=job.get("config"),
            features=job.get("features"),
            scripts=state.get("scripts"),
            country_profile=state.get("country_profile"),
            region_profile=state.get("region_profile"),
            locale_pack=state.get("locale_pack"),
        )
    except LanguageAgentError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=9,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[language] Failed: {exc}")
        return {
            "current_step": 10,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "localizations": None,
        }

    steps = _mark_localization_running(
        state.get("steps", initial_progress_steps())
    )
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "current_step": 9,
        "steps": steps,
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_language(state: WorkflowState) -> str:
    return route_after_language(state)


def _language_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Language localization failed",
    }


def _skip_cultural_node(state: WorkflowState) -> dict[str, Any]:
    project = state.get("project") or {}
    features = dict((state.get("job") or {}).get("features") or {})
    features["cultural_adaptation"] = False
    job = state.get("job") or {}
    result = CulturalAdaptationAgent().run(
        project,
        project_dir=state.get("project_dir"),
        config=job.get("config"),
        features=features,
        scripts=state.get("scripts"),
        locale_pack=state.get("locale_pack"),
        country_profile=state.get("country_profile"),
        region_profile=state.get("region_profile"),
    )
    messages = list(state.get("messages") or [])
    messages.append("[cultural] Skipped (feature off)")
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _skip_humor_node(state: WorkflowState) -> dict[str, Any]:
    project = state.get("project") or {}
    features = dict((state.get("job") or {}).get("features") or {})
    features["regional_humor"] = False
    job = dict(state.get("job") or {})
    cfg = dict(job.get("config") or {})
    cfg["humor_adaptation"] = "none"
    job["config"] = cfg
    result = HumorLocalizationAgent().run(
        project,
        project_dir=state.get("project_dir"),
        config=cfg,
        features=features,
        scripts=state.get("scripts"),
        locale_pack=state.get("locale_pack"),
        country_profile=state.get("country_profile"),
        region_profile=state.get("region_profile"),
    )
    messages = list(state.get("messages") or [])
    messages.append("[humor] Skipped (feature off)")
    messages.extend(result.messages)
    steps = _mark_steps_completed(
        state.get("steps", initial_progress_steps()),
        completed_through=10,
    )
    return {
        **result.to_state_dict(),
        "current_step": 10,
        "steps": steps,
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _skip_broll_node(state: WorkflowState) -> dict[str, Any]:
    project = state.get("project") or {}
    features = dict((state.get("job") or {}).get("features") or {})
    features["b_roll"] = False
    job = state.get("job") or {}
    result = BRollAgent().run(
        project,
        project_dir=state.get("project_dir"),
        config=job.get("config"),
        features=features,
        clips=state.get("clips"),
        scripts=state.get("scripts"),
        environment_pack=state.get("environment_pack"),
    )
    messages = list(state.get("messages") or [])
    messages.append("[b_roll] Skipped (feature off)")
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "steps": _step11_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _skip_storyboard_node(state: WorkflowState) -> dict[str, Any]:
    project = state.get("project") or {}
    features = dict((state.get("job") or {}).get("features") or {})
    features["storyboard"] = False
    job = state.get("job") or {}
    result = StoryboardAgent().run(
        project,
        project_dir=state.get("project_dir"),
        config=job.get("config"),
        features=features,
        script_pack=state.get("scripts"),
        transcript=state.get("transcript") or state.get("speech_transcript"),
        scenes=state.get("scenes"),
        stories=state.get("stories"),
        visual_style_pack=state.get("visual_style_pack"),
        environment_pack=state.get("environment_pack"),
    )
    messages = list(state.get("messages") or [])
    messages.append("[storyboard] Skipped (feature off)")
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "steps": _step11_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _storyboard_node(state: WorkflowState) -> dict[str, Any]:
    """Storyboard Agent: write analysis/storyboard_plan.json (under step 11)."""
    project = state.get("project")
    if not project:
        return {
            "status": JobStatus.FAILED.value,
            "error": "Missing project for storyboard planning",
            "storyboard_pack": None,
        }
    job = state.get("job") or {}
    try:
        result = StoryboardAgent().run(
            project,
            project_dir=state.get("project_dir"),
            config=job.get("config"),
            features=job.get("features"),
            script_pack=state.get("scripts"),
            transcript=state.get("transcript") or state.get("speech_transcript"),
            scenes=state.get("scenes"),
            stories=state.get("stories"),
            visual_style_pack=state.get("visual_style_pack"),
            environment_pack=state.get("environment_pack"),
        )
    except StoryboardAgentError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=10,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[storyboard] Failed: {exc}")
        return {
            "current_step": 11,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "storyboard_pack": None,
        }
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "steps": _step11_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_storyboard(state: WorkflowState) -> str:
    return route_after_storyboard(state)


def _storyboard_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Storyboard planning failed",
    }


def _skip_character_node(state: WorkflowState) -> dict[str, Any]:
    project = state.get("project") or {}
    features = dict((state.get("job") or {}).get("features") or {})
    features["character"] = False
    job = state.get("job") or {}
    result = CharacterAgent().run(
        project,
        project_dir=state.get("project_dir"),
        config=job.get("config"),
        features=features,
        script_pack=state.get("scripts"),
        storyboard_pack=state.get("storyboard_pack"),
        stories=state.get("stories"),
        visual_style_pack=state.get("visual_style_pack"),
        environment_pack=state.get("environment_pack"),
    )
    messages = list(state.get("messages") or [])
    messages.append("[character] Skipped (feature off)")
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "steps": _step11_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _character_node(state: WorkflowState) -> dict[str, Any]:
    """Character Management Agent: write analysis/character_plan.json."""
    project = state.get("project")
    if not project:
        return {
            "status": JobStatus.FAILED.value,
            "error": "Missing project for character planning",
            "character_pack": None,
        }
    job = state.get("job") or {}
    try:
        result = CharacterAgent().run(
            project,
            project_dir=state.get("project_dir"),
            config=job.get("config"),
            features=job.get("features"),
            script_pack=state.get("scripts"),
            storyboard_pack=state.get("storyboard_pack"),
            stories=state.get("stories"),
            visual_style_pack=state.get("visual_style_pack"),
            environment_pack=state.get("environment_pack"),
        )
    except CharacterAgentError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=10,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[character] Failed: {exc}")
        return {
            "current_step": 11,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "character_pack": None,
        }
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "steps": _step11_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_character(state: WorkflowState) -> str:
    return route_after_character(state)


def _character_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Character planning failed",
    }


def _skip_camera_node(state: WorkflowState) -> dict[str, Any]:
    project = state.get("project") or {}
    features = dict((state.get("job") or {}).get("features") or {})
    features["camera"] = False
    job = state.get("job") or {}
    result = CameraAgent().run(
        project,
        project_dir=state.get("project_dir"),
        config=job.get("config"),
        features=features,
        script_pack=state.get("scripts"),
        storyboard_pack=state.get("storyboard_pack"),
        character_pack=state.get("character_pack"),
        visual_style_pack=state.get("visual_style_pack"),
        environment_pack=state.get("environment_pack"),
    )
    messages = list(state.get("messages") or [])
    messages.append("[camera] Skipped (feature off)")
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "steps": _step11_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _camera_node(state: WorkflowState) -> dict[str, Any]:
    """Camera Planning Agent: write analysis/camera_plan.json."""
    project = state.get("project")
    if not project:
        return {
            "status": JobStatus.FAILED.value,
            "error": "Missing project for camera planning",
            "camera_pack": None,
        }
    job = state.get("job") or {}
    try:
        result = CameraAgent().run(
            project,
            project_dir=state.get("project_dir"),
            config=job.get("config"),
            features=job.get("features"),
            script_pack=state.get("scripts"),
            storyboard_pack=state.get("storyboard_pack"),
            character_pack=state.get("character_pack"),
            visual_style_pack=state.get("visual_style_pack"),
            environment_pack=state.get("environment_pack"),
        )
    except CameraAgentError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=10,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[camera] Failed: {exc}")
        return {
            "current_step": 11,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "camera_pack": None,
        }
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "steps": _step11_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_camera(state: WorkflowState) -> str:
    return route_after_camera(state)


def _camera_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Camera planning failed",
    }


def _skip_director_node(state: WorkflowState) -> dict[str, Any]:
    project = state.get("project") or {}
    features = dict((state.get("job") or {}).get("features") or {})
    features["director"] = False
    job = state.get("job") or {}
    result = DirectorAgent().run(
        project,
        project_dir=state.get("project_dir"),
        config=job.get("config"),
        features=features,
        script_pack=state.get("scripts"),
        storyboard_pack=state.get("storyboard_pack"),
        stories=state.get("stories"),
        visual_style_pack=state.get("visual_style_pack"),
        environment_pack=state.get("environment_pack"),
        character_pack=state.get("character_pack"),
        camera_pack=state.get("camera_pack"),
    )
    messages = list(state.get("messages") or [])
    messages.append("[director] Skipped (feature off)")
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "steps": _step11_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _director_node(state: WorkflowState) -> dict[str, Any]:
    """Director Agent: write analysis/director_plan.json."""
    project = state.get("project")
    if not project:
        return {
            "status": JobStatus.FAILED.value,
            "error": "Missing project for director planning",
            "director_pack": None,
        }
    job = state.get("job") or {}
    try:
        result = DirectorAgent().run(
            project,
            project_dir=state.get("project_dir"),
            config=job.get("config"),
            features=job.get("features"),
            script_pack=state.get("scripts"),
            storyboard_pack=state.get("storyboard_pack"),
            stories=state.get("stories"),
            visual_style_pack=state.get("visual_style_pack"),
            environment_pack=state.get("environment_pack"),
            character_pack=state.get("character_pack"),
            camera_pack=state.get("camera_pack"),
        )
    except DirectorAgentError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=10,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[director] Failed: {exc}")
        return {
            "current_step": 11,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "director_pack": None,
        }
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "steps": _step11_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_director(state: WorkflowState) -> str:
    return route_after_director(state)


def _director_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Director planning failed",
    }


def _skip_motion_graphics_node(state: WorkflowState) -> dict[str, Any]:
    project = state.get("project") or {}
    features = dict((state.get("job") or {}).get("features") or {})
    features["motion_graphics"] = False
    job = state.get("job") or {}
    result = MotionGraphicsAgent().run(
        project,
        project_dir=state.get("project_dir"),
        config=job.get("config"),
        features=features,
        script_pack=state.get("scripts"),
        storyboard_pack=state.get("storyboard_pack"),
        director_pack=state.get("director_pack"),
        camera_pack=state.get("camera_pack"),
        character_pack=state.get("character_pack"),
        visual_style_pack=state.get("visual_style_pack"),
    )
    messages = list(state.get("messages") or [])
    messages.append("[motion_graphics] Skipped (feature off)")
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "steps": _step11_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _motion_graphics_node(state: WorkflowState) -> dict[str, Any]:
    """Motion Graphics Agent: write analysis/motion_graphics_plan.json."""
    project = state.get("project")
    if not project:
        return {
            "status": JobStatus.FAILED.value,
            "error": "Missing project for motion graphics planning",
            "motion_graphics_pack": None,
        }
    job = state.get("job") or {}
    try:
        result = MotionGraphicsAgent().run(
            project,
            project_dir=state.get("project_dir"),
            config=job.get("config"),
            features=job.get("features"),
            script_pack=state.get("scripts"),
            storyboard_pack=state.get("storyboard_pack"),
            director_pack=state.get("director_pack"),
            camera_pack=state.get("camera_pack"),
            character_pack=state.get("character_pack"),
            visual_style_pack=state.get("visual_style_pack"),
        )
    except MotionGraphicsAgentError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=10,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[motion_graphics] Failed: {exc}")
        return {
            "current_step": 11,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "motion_graphics_pack": None,
        }
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "steps": _step11_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_motion_graphics(state: WorkflowState) -> str:
    return route_after_motion_graphics(state)


def _motion_graphics_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Motion graphics planning failed",
    }


def _skip_documentary_node(state: WorkflowState) -> dict[str, Any]:
    project = state.get("project") or {}
    features = dict((state.get("job") or {}).get("features") or {})
    features["documentary"] = False
    job = state.get("job") or {}
    result = DocumentaryAgent().run(
        project,
        project_dir=state.get("project_dir"),
        config=job.get("config"),
        features=features,
        script_pack=state.get("scripts"),
        storyboard_pack=state.get("storyboard_pack"),
        director_pack=state.get("director_pack"),
        character_pack=state.get("character_pack"),
        visual_style_pack=state.get("visual_style_pack"),
    )
    messages = list(state.get("messages") or [])
    messages.append("[documentary] Skipped (feature off)")
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "steps": _step11_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _documentary_node(state: WorkflowState) -> dict[str, Any]:
    """Documentary Agent: write analysis/documentary_plan.json."""
    project = state.get("project")
    if not project:
        return {
            "status": JobStatus.FAILED.value,
            "error": "Missing project for documentary planning",
            "documentary_pack": None,
        }
    job = state.get("job") or {}
    try:
        result = DocumentaryAgent().run(
            project,
            project_dir=state.get("project_dir"),
            config=job.get("config"),
            features=job.get("features"),
            script_pack=state.get("scripts"),
            storyboard_pack=state.get("storyboard_pack"),
            director_pack=state.get("director_pack"),
            character_pack=state.get("character_pack"),
            visual_style_pack=state.get("visual_style_pack"),
        )
    except DocumentaryAgentError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=10,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[documentary] Failed: {exc}")
        return {
            "current_step": 11,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "documentary_pack": None,
        }
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "steps": _step11_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_documentary(state: WorkflowState) -> str:
    return route_after_documentary(state)


def _documentary_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Documentary planning failed",
    }


def _skip_video_generation_node(state: WorkflowState) -> dict[str, Any]:
    project = state.get("project") or {}
    features = dict((state.get("job") or {}).get("features") or {})
    features["video_generation"] = False
    job = state.get("job") or {}
    result = VideoGenerationAgent().run(
        project,
        project_dir=state.get("project_dir"),
        config=job.get("config"),
        features=features,
        script_pack=state.get("scripts"),
        storyboard_pack=state.get("storyboard_pack"),
        visual_style_pack=state.get("visual_style_pack"),
        environment_pack=state.get("environment_pack"),
        director_pack=state.get("director_pack"),
        character_pack=state.get("character_pack"),
        camera_pack=state.get("camera_pack"),
        motion_graphics_pack=state.get("motion_graphics_pack"),
        documentary_pack=state.get("documentary_pack"),
    )
    messages = list(state.get("messages") or [])
    messages.append("[video_generation] Skipped (feature off)")
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "steps": _step11_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _video_generation_node(state: WorkflowState) -> dict[str, Any]:
    """Video Generation Agent: write analysis/video_generation_plan.json."""
    project = state.get("project")
    if not project:
        return {
            "status": JobStatus.FAILED.value,
            "error": "Missing project for video generation planning",
            "video_generation_pack": None,
        }
    job = state.get("job") or {}
    try:
        result = VideoGenerationAgent().run(
            project,
            project_dir=state.get("project_dir"),
            config=job.get("config"),
            features=job.get("features"),
            script_pack=state.get("scripts"),
            storyboard_pack=state.get("storyboard_pack"),
            visual_style_pack=state.get("visual_style_pack"),
            environment_pack=state.get("environment_pack"),
            director_pack=state.get("director_pack"),
            character_pack=state.get("character_pack"),
            camera_pack=state.get("camera_pack"),
            motion_graphics_pack=state.get("motion_graphics_pack"),
            documentary_pack=state.get("documentary_pack"),
        )
    except VideoGenerationAgentError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=10,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[video_generation] Failed: {exc}")
        return {
            "current_step": 11,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "video_generation_pack": None,
        }
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "steps": _step11_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_video_generation(state: WorkflowState) -> str:
    return route_after_video_generation(state)


def _video_generation_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Video generation planning failed",
    }


def _skip_image_generation_node(state: WorkflowState) -> dict[str, Any]:
    project = state.get("project") or {}
    features = dict((state.get("job") or {}).get("features") or {})
    features["image_generation"] = False
    job = state.get("job") or {}
    result = ImageAgent().run(
        project,
        project_dir=state.get("project_dir"),
        config=job.get("config"),
        features=features,
        script_pack=state.get("scripts"),
        transcript=state.get("transcript") or state.get("speech_transcript"),
        scenes=state.get("scenes"),
        stories=state.get("stories"),
        visual_style_pack=state.get("visual_style_pack"),
        environment_pack=state.get("environment_pack"),
    )
    messages = list(state.get("messages") or [])
    messages.append("[image_generation] Skipped (feature off)")
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "steps": _step11_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _image_generation_node(state: WorkflowState) -> dict[str, Any]:
    """Image Agent: write analysis/image_plan.json + images/ assets."""
    project = state.get("project")
    if not project:
        return {
            "status": JobStatus.FAILED.value,
            "error": "Missing project for image generation",
            "image_pack": None,
        }
    job = state.get("job") or {}
    try:
        result = ImageAgent().run(
            project,
            project_dir=state.get("project_dir"),
            config=job.get("config"),
            features=job.get("features"),
            script_pack=state.get("scripts"),
            transcript=state.get("transcript") or state.get("speech_transcript"),
            scenes=state.get("scenes"),
            stories=state.get("stories"),
            visual_style_pack=state.get("visual_style_pack"),
            environment_pack=state.get("environment_pack"),
        )
    except ImageAgentError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=10,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[image_generation] Failed: {exc}")
        return {
            "current_step": 11,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "image_pack": None,
        }
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "steps": _step11_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_image_generation(state: WorkflowState) -> str:
    return route_after_image_generation(state)


def _image_generation_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Image generation failed",
    }


def _skip_voice_node(state: WorkflowState) -> dict[str, Any]:
    project = state.get("project") or {}
    features = dict((state.get("job") or {}).get("features") or {})
    features["voice"] = False
    job = state.get("job") or {}
    result = VoiceAgent().run(
        project,
        project_dir=state.get("project_dir"),
        config=job.get("config"),
        features=features,
        scripts=state.get("scripts"),
        locale_pack=state.get("locale_pack"),
        localizations=state.get("localizations"),
        transcript=state.get("transcript"),
        speech_transcript=state.get("speech_transcript"),
    )
    messages = list(state.get("messages") or [])
    messages.append("[voice] Skipped (original / feature off)")
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "steps": _step11_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _skip_music_node(state: WorkflowState) -> dict[str, Any]:
    project = state.get("project") or {}
    features = dict((state.get("job") or {}).get("features") or {})
    features["music"] = False
    job = state.get("job") or {}
    result = MusicAgent().run(
        project,
        project_dir=state.get("project_dir"),
        config=job.get("config"),
        features=features,
        scripts=state.get("scripts"),
        voice_pack=state.get("voice_pack"),
    )
    messages = list(state.get("messages") or [])
    messages.append("[music] Skipped (no music / feature off)")
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "steps": _step11_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _step11_running(state: WorkflowState) -> list[dict[str, Any]]:
    """Keep Captions step RUNNING while B-roll/Voice/Music plan."""
    steps = list(state.get("steps") or initial_progress_steps())
    steps = [dict(s) for s in steps]
    for i, step in enumerate(steps):
        if i <= 10:
            step["status"] = ProgressStepStatus.COMPLETED.value
        elif i == 11:
            step["status"] = ProgressStepStatus.RUNNING.value
        else:
            step["status"] = ProgressStepStatus.PENDING.value
    return steps


def _broll_node(state: WorkflowState) -> dict[str, Any]:
    """B-Roll Agent: write analysis/broll_plan.json (under step 11)."""
    project = state.get("project")
    if not project:
        return {
            "status": JobStatus.FAILED.value,
            "error": "Missing project for B-roll planning",
            "broll_pack": None,
        }
    job = state.get("job") or {}
    try:
        result = BRollAgent().run(
            project,
            project_dir=state.get("project_dir"),
            config=job.get("config"),
            features=job.get("features"),
            clips=state.get("clips"),
            scripts=state.get("scripts"),
            environment_pack=state.get("environment_pack"),
        )
    except BRollAgentError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=10,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[b_roll] Failed: {exc}")
        return {
            "current_step": 11,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "broll_pack": None,
        }
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "current_step": 10,
        "steps": _step11_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_broll(state: WorkflowState) -> str:
    return route_after_broll(state)


def _broll_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "B-roll planning failed",
    }


def _voice_node(state: WorkflowState) -> dict[str, Any]:
    """Voice Agent: write analysis/voice_plan.json (under step 11)."""
    project = state.get("project")
    if not project:
        return {
            "status": JobStatus.FAILED.value,
            "error": "Missing project for voice planning",
            "voice_pack": None,
        }
    job = state.get("job") or {}
    try:
        result = VoiceAgent().run(
            project,
            project_dir=state.get("project_dir"),
            config=job.get("config"),
            features=job.get("features"),
            locale_pack=state.get("locale_pack"),
            localizations=state.get("localizations"),
            scripts=state.get("scripts"),
            transcript=state.get("transcript"),
            speech_transcript=state.get("speech_transcript"),
        )
    except VoiceAgentError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=10,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[voice] Failed: {exc}")
        return {
            "current_step": 11,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "voice_pack": None,
        }
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "current_step": 10,
        "steps": _step11_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_voice(state: WorkflowState) -> str:
    return route_after_voice(state)


def _voice_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Voice planning failed",
    }


def _skip_avatar_node(state: WorkflowState) -> dict[str, Any]:
    project = state.get("project") or {}
    features = dict((state.get("job") or {}).get("features") or {})
    features["avatar"] = False
    job = state.get("job") or {}
    result = AvatarAgent().run(
        project,
        project_dir=state.get("project_dir"),
        config=job.get("config"),
        features=features,
        voice_pack=state.get("voice_pack"),
        locale_pack=state.get("locale_pack"),
        localizations=state.get("localizations"),
    )
    messages = list(state.get("messages") or [])
    messages.append("[avatar] Skipped (no avatar / feature off)")
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "steps": _step11_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _avatar_node(state: WorkflowState) -> dict[str, Any]:
    """Avatar Agent: write analysis/avatar_plan.json (under step 11)."""
    project = state.get("project")
    if not project:
        return {
            "status": JobStatus.FAILED.value,
            "error": "Missing project for avatar planning",
            "avatar_pack": None,
        }
    job = state.get("job") or {}
    try:
        result = AvatarAgent().run(
            project,
            project_dir=state.get("project_dir"),
            config=job.get("config"),
            features=job.get("features"),
            voice_pack=state.get("voice_pack"),
            locale_pack=state.get("locale_pack"),
            localizations=state.get("localizations"),
        )
    except AvatarAgentError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=10,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[avatar] Failed: {exc}")
        return {
            "current_step": 11,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "avatar_pack": None,
        }
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "current_step": 10,
        "steps": _step11_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_avatar(state: WorkflowState) -> str:
    return route_after_avatar(state)


def _avatar_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Avatar planning failed",
    }


def _music_node(state: WorkflowState) -> dict[str, Any]:
    """Music Agent: write analysis/music_plan.json (under step 11)."""
    project = state.get("project")
    if not project:
        return {
            "status": JobStatus.FAILED.value,
            "error": "Missing project for music planning",
            "music_pack": None,
        }
    job = state.get("job") or {}
    try:
        result = MusicAgent().run(
            project,
            project_dir=state.get("project_dir"),
            config=job.get("config"),
            features=job.get("features"),
        )
    except MusicAgentError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=10,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[music] Failed: {exc}")
        return {
            "current_step": 11,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "music_pack": None,
        }
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "current_step": 10,
        "steps": _step11_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_music(state: WorkflowState) -> str:
    return route_after_music(state)


def _music_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Music planning failed",
    }


def _captions_node(state: WorkflowState) -> dict[str, Any]:
    """Caption Agent: timed cues + SRT/VTT/ASS (+ optional burn-in); completes step 11."""
    project = state.get("project")
    if not project:
        return {
            "status": JobStatus.FAILED.value,
            "error": "Missing project for caption generation",
            "captions_pack": None,
        }
    job = state.get("job") or {}
    try:
        result = CaptionAgent().run(
            project,
            project_dir=state.get("project_dir"),
            config=job.get("config"),
            features=job.get("features"),
            speech_transcript=state.get("speech_transcript"),
            transcript=state.get("transcript"),
            localizations=state.get("localizations"),
            locale_pack=state.get("locale_pack"),
            source_metadata=state.get("source_metadata"),
        )
    except CaptionAgentError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=10,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[captions] Failed: {exc}")
        return {
            "current_step": 11,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "captions_pack": None,
        }
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "current_step": 11,
        "steps": _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=11,
        ),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_captions(state: WorkflowState) -> str:
    if state.get("status") == JobStatus.FAILED.value or state.get("error"):
        return "captions_failed"
    return "continue"


def _captions_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Caption generation failed",
    }


def _reframe_node(state: WorkflowState) -> dict[str, Any]:
    """Smart Reframe Agent: plan first, optional FFmpeg encode; completes step 12."""
    project = state.get("project")
    if not project:
        return {
            "status": JobStatus.FAILED.value,
            "error": "Missing project for smart reframing",
            "reframe_pack": None,
        }
    job = state.get("job") or {}
    try:
        result = ReframeAgent().run(
            project,
            project_dir=state.get("project_dir"),
            config=job.get("config"),
            features=job.get("features"),
            clips=state.get("clips"),
            analysis=state.get("analysis"),
            speakers=state.get("speakers"),
            video_type_pack=state.get("video_type_pack"),
            source_metadata=state.get("source_metadata"),
            speech_transcript=state.get("speech_transcript"),
        )
    except ReframeAgentError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=11,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[smart_reframe] Failed: {exc}")
        return {
            "current_step": 12,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "reframe_pack": None,
        }
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "current_step": 12,
        "steps": _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=12,
        ),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_reframe(state: WorkflowState) -> str:
    if state.get("status") == JobStatus.FAILED.value or state.get("error"):
        return "reframe_failed"
    return "continue"


def _reframe_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Smart reframing failed",
    }


def _platform_node(state: WorkflowState) -> dict[str, Any]:
    """Platform Agent: optimize export metadata; completes step 13."""
    project = state.get("project")
    if not project:
        return {
            "status": JobStatus.FAILED.value,
            "error": "Missing project for platform optimization",
            "platform_pack": None,
        }
    job = state.get("job") or {}
    try:
        result = PlatformAgent().run(
            project,
            project_dir=state.get("project_dir"),
            config=job.get("config"),
            features=job.get("features"),
            scripts=state.get("scripts"),
            localizations=state.get("localizations"),
            video_type_pack=state.get("video_type_pack"),
            captions_pack=state.get("captions_pack"),
            reframe_pack=state.get("reframe_pack"),
            locale_pack=state.get("locale_pack"),
        )
    except PlatformAgentError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=12,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[platform] Failed: {exc}")
        return {
            "current_step": 13,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "platform_pack": None,
        }
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "current_step": 13,
        "steps": _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=13,
        ),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_platform(state: WorkflowState) -> str:
    return route_after_platform(state)


def _platform_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Platform optimization failed",
    }


def _skip_brand_node(state: WorkflowState) -> dict[str, Any]:
    project = state.get("project") or {}
    features = dict((state.get("job") or {}).get("features") or {})
    features["brand"] = False
    job = state.get("job") or {}
    result = BrandAgent().run(
        project,
        project_dir=state.get("project_dir"),
        config=job.get("config"),
        features=features,
        platform_pack=state.get("platform_pack"),
        visual_style_pack=state.get("visual_style_pack"),
    )
    messages = list(state.get("messages") or [])
    messages.append("[brand] Skipped (feature off)")
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "steps": _step14_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _brand_node(state: WorkflowState) -> dict[str, Any]:
    """Brand Agent: write analysis/brand_plan.json (under export milestone)."""
    project = state.get("project")
    if not project:
        return {
            "status": JobStatus.FAILED.value,
            "error": "Missing project for brand planning",
            "brand_pack": None,
        }
    job = state.get("job") or {}
    try:
        result = BrandAgent().run(
            project,
            project_dir=state.get("project_dir"),
            config=job.get("config"),
            features=job.get("features"),
            platform_pack=state.get("platform_pack"),
            visual_style_pack=state.get("visual_style_pack"),
        )
    except BrandAgentError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=13,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[brand] Failed: {exc}")
        return {
            "current_step": 14,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "brand_pack": None,
        }
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "steps": _step14_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_brand(state: WorkflowState) -> str:
    return route_after_brand(state)


def _brand_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Brand planning failed",
    }


def _skip_seo_node(state: WorkflowState) -> dict[str, Any]:
    project = state.get("project") or {}
    features = dict((state.get("job") or {}).get("features") or {})
    features["seo"] = False
    job = state.get("job") or {}
    result = SeoAgent().run(
        project,
        project_dir=state.get("project_dir"),
        config=job.get("config"),
        features=features,
        script_pack=state.get("scripts"),
        platform_pack=state.get("platform_pack"),
        brand_pack=state.get("brand_pack"),
    )
    messages = list(state.get("messages") or [])
    messages.append("[seo] Skipped (feature off)")
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "steps": _step14_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _seo_node(state: WorkflowState) -> dict[str, Any]:
    """SEO Agent: write analysis/seo_plan.json (under export milestone)."""
    project = state.get("project")
    if not project:
        return {
            "status": JobStatus.FAILED.value,
            "error": "Missing project for SEO planning",
            "seo_pack": None,
        }
    job = state.get("job") or {}
    try:
        result = SeoAgent().run(
            project,
            project_dir=state.get("project_dir"),
            config=job.get("config"),
            features=job.get("features"),
            script_pack=state.get("scripts"),
            platform_pack=state.get("platform_pack"),
            brand_pack=state.get("brand_pack"),
        )
    except SeoAgentError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=13,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[seo] Failed: {exc}")
        return {
            "current_step": 14,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "seo_pack": None,
        }
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "steps": _step14_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_seo(state: WorkflowState) -> str:
    return route_after_seo(state)


def _seo_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "SEO planning failed",
    }


def _skip_trend_node(state: WorkflowState) -> dict[str, Any]:
    project = state.get("project") or {}
    features = dict((state.get("job") or {}).get("features") or {})
    features["trend"] = False
    job = state.get("job") or {}
    result = TrendAgent().run(
        project,
        project_dir=state.get("project_dir"),
        config=job.get("config"),
        features=features,
        script_pack=state.get("scripts"),
        platform_pack=state.get("platform_pack"),
        seo_pack=state.get("seo_pack"),
        viral_pack=state.get("viral_moments"),
        brand_pack=state.get("brand_pack"),
    )
    messages = list(state.get("messages") or [])
    messages.append("[trend] Skipped (feature off)")
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "steps": _step14_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _trend_node(state: WorkflowState) -> dict[str, Any]:
    """Trend Agent: write analysis/trend_plan.json (under export milestone)."""
    project = state.get("project")
    if not project:
        return {
            "status": JobStatus.FAILED.value,
            "error": "Missing project for trend planning",
            "trend_pack": None,
        }
    job = state.get("job") or {}
    try:
        result = TrendAgent().run(
            project,
            project_dir=state.get("project_dir"),
            config=job.get("config"),
            features=job.get("features"),
            script_pack=state.get("scripts"),
            platform_pack=state.get("platform_pack"),
            seo_pack=state.get("seo_pack"),
            viral_pack=state.get("viral_moments"),
            brand_pack=state.get("brand_pack"),
        )
    except TrendAgentError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=13,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[trend] Failed: {exc}")
        return {
            "current_step": 14,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "trend_pack": None,
        }
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "steps": _step14_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_trend(state: WorkflowState) -> str:
    return route_after_trend(state)


def _trend_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Trend planning failed",
    }


def _skip_repurpose_node(state: WorkflowState) -> dict[str, Any]:
    project = state.get("project") or {}
    features = dict((state.get("job") or {}).get("features") or {})
    features["repurpose"] = False
    job = state.get("job") or {}
    result = RepurposeAgent().run(
        project,
        project_dir=state.get("project_dir"),
        config=job.get("config"),
        features=features,
        script_pack=state.get("scripts"),
        transcript=state.get("transcript"),
        speech_transcript=state.get("speech_transcript"),
        seo_pack=state.get("seo_pack"),
        trend_pack=state.get("trend_pack"),
        platform_pack=state.get("platform_pack"),
        brand_pack=state.get("brand_pack"),
    )
    messages = list(state.get("messages") or [])
    messages.append("[repurpose] Skipped (feature off)")
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "steps": _step14_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _repurpose_node(state: WorkflowState) -> dict[str, Any]:
    """Repurpose Agent: write analysis/repurpose_plan.json (under export milestone)."""
    project = state.get("project")
    if not project:
        return {
            "status": JobStatus.FAILED.value,
            "error": "Missing project for content repurposing",
            "repurpose_pack": None,
        }
    job = state.get("job") or {}
    try:
        result = RepurposeAgent().run(
            project,
            project_dir=state.get("project_dir"),
            config=job.get("config"),
            features=job.get("features"),
            script_pack=state.get("scripts"),
            transcript=state.get("transcript"),
            speech_transcript=state.get("speech_transcript"),
            seo_pack=state.get("seo_pack"),
            trend_pack=state.get("trend_pack"),
            platform_pack=state.get("platform_pack"),
            brand_pack=state.get("brand_pack"),
        )
    except RepurposeAgentError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=13,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[repurpose] Failed: {exc}")
        return {
            "current_step": 14,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "repurpose_pack": None,
        }
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "steps": _step14_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_repurpose(state: WorkflowState) -> str:
    return route_after_repurpose(state)


def _repurpose_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Content repurposing failed",
    }


def _skip_calendar_node(state: WorkflowState) -> dict[str, Any]:
    project = state.get("project") or {}
    features = dict((state.get("job") or {}).get("features") or {})
    features["content_calendar"] = False
    job = state.get("job") or {}
    result = ContentCalendarAgent().run(
        project,
        project_dir=state.get("project_dir"),
        config=job.get("config"),
        features=features,
        script_pack=state.get("scripts"),
        research_report=state.get("research_report"),
        trend_pack=state.get("trend_pack"),
        repurpose_pack=state.get("repurpose_pack"),
        video_type_pack=state.get("video_type_pack"),
        platform_pack=state.get("platform_pack"),
        brand_pack=state.get("brand_pack"),
    )
    messages = list(state.get("messages") or [])
    messages.append("[content_calendar] Skipped (feature off)")
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "steps": _step14_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _calendar_node(state: WorkflowState) -> dict[str, Any]:
    """Content Calendar Agent: write analysis/calendar_plan.json."""
    project = state.get("project")
    if not project:
        return {
            "status": JobStatus.FAILED.value,
            "error": "Missing project for content calendar",
            "calendar_pack": None,
        }
    job = state.get("job") or {}
    try:
        result = ContentCalendarAgent().run(
            project,
            project_dir=state.get("project_dir"),
            config=job.get("config"),
            features=job.get("features"),
            script_pack=state.get("scripts"),
            research_report=state.get("research_report"),
            trend_pack=state.get("trend_pack"),
            repurpose_pack=state.get("repurpose_pack"),
            video_type_pack=state.get("video_type_pack"),
            platform_pack=state.get("platform_pack"),
            brand_pack=state.get("brand_pack"),
        )
    except CalendarAgentError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=13,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[content_calendar] Failed: {exc}")
        return {
            "current_step": 14,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "calendar_pack": None,
        }
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "steps": _step14_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_calendar(state: WorkflowState) -> str:
    return route_after_calendar(state)


def _calendar_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Content calendar planning failed",
    }


def _skip_thumbnail_node(state: WorkflowState) -> dict[str, Any]:
    project = state.get("project") or {}
    features = dict((state.get("job") or {}).get("features") or {})
    features["thumbnail"] = False
    job = state.get("job") or {}
    result = ThumbnailAgent().run(
        project,
        project_dir=state.get("project_dir"),
        config=job.get("config"),
        features=features,
        script_pack=state.get("scripts"),
        platform_pack=state.get("platform_pack"),
        viral_pack=state.get("viral_moments"),
        seo_pack=state.get("seo_pack"),
        trend_pack=state.get("trend_pack"),
        brand_pack=state.get("brand_pack"),
    )
    messages = list(state.get("messages") or [])
    messages.append("[thumbnail] Skipped (feature off)")
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "steps": _step14_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _thumbnail_node(state: WorkflowState) -> dict[str, Any]:
    """Thumbnail Agent: write analysis/thumbnail_plan.json (under export milestone)."""
    project = state.get("project")
    if not project:
        return {
            "status": JobStatus.FAILED.value,
            "error": "Missing project for thumbnail planning",
            "thumbnail_pack": None,
        }
    job = state.get("job") or {}
    try:
        result = ThumbnailAgent().run(
            project,
            project_dir=state.get("project_dir"),
            config=job.get("config"),
            features=job.get("features"),
            script_pack=state.get("scripts"),
            platform_pack=state.get("platform_pack"),
            viral_pack=state.get("viral_moments"),
            seo_pack=state.get("seo_pack"),
            trend_pack=state.get("trend_pack"),
            brand_pack=state.get("brand_pack"),
        )
    except ThumbnailAgentError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=13,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[thumbnail] Failed: {exc}")
        return {
            "current_step": 14,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "thumbnail_pack": None,
        }
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "steps": _step14_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_thumbnail(state: WorkflowState) -> str:
    return route_after_thumbnail(state)


def _thumbnail_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Thumbnail planning failed",
    }


def _skip_analytics_node(state: WorkflowState) -> dict[str, Any]:
    project = state.get("project") or {}
    features = dict((state.get("job") or {}).get("features") or {})
    features["analytics"] = False
    job = state.get("job") or {}
    result = AnalyticsAgent().run(
        project,
        project_dir=state.get("project_dir"),
        config=job.get("config"),
        features=features,
        script_pack=state.get("scripts"),
        platform_pack=state.get("platform_pack"),
        seo_pack=state.get("seo_pack"),
        trend_pack=state.get("trend_pack"),
        repurpose_pack=state.get("repurpose_pack"),
        thumbnail_pack=state.get("thumbnail_pack"),
        viral_pack=state.get("viral_moments"),
    )
    messages = list(state.get("messages") or [])
    messages.append("[analytics] Skipped (feature off)")
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "steps": _step14_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _analytics_node(state: WorkflowState) -> dict[str, Any]:
    """Analytics Agent: write analysis/analytics_plan.json (under export milestone)."""
    project = state.get("project")
    if not project:
        return {
            "status": JobStatus.FAILED.value,
            "error": "Missing project for analytics prediction",
            "analytics_pack": None,
        }
    job = state.get("job") or {}
    try:
        result = AnalyticsAgent().run(
            project,
            project_dir=state.get("project_dir"),
            config=job.get("config"),
            features=job.get("features"),
            script_pack=state.get("scripts"),
            platform_pack=state.get("platform_pack"),
            seo_pack=state.get("seo_pack"),
            trend_pack=state.get("trend_pack"),
            repurpose_pack=state.get("repurpose_pack"),
            thumbnail_pack=state.get("thumbnail_pack"),
            viral_pack=state.get("viral_moments"),
        )
    except AnalyticsAgentError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=13,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[analytics] Failed: {exc}")
        return {
            "current_step": 14,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "analytics_pack": None,
        }
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "steps": _step14_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_analytics(state: WorkflowState) -> str:
    return route_after_analytics(state)


def _analytics_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Analytics prediction failed",
    }


def _step14_running(state: WorkflowState) -> list[dict[str, Any]]:
    """Keep Export completed step RUNNING while Render/Quality resolve."""
    steps = list(state.get("steps") or initial_progress_steps())
    steps = [dict(s) for s in steps]
    for i, step in enumerate(steps):
        if i <= 13:
            step["status"] = ProgressStepStatus.COMPLETED.value
        elif i == 14:
            step["status"] = ProgressStepStatus.RUNNING.value
        else:
            step["status"] = ProgressStepStatus.PENDING.value
    return steps


def _render_node(state: WorkflowState) -> dict[str, Any]:
    """Render Agent: compose final.mp4; step 14 stays RUNNING."""
    project = state.get("project")
    if not project:
        return {
            "status": JobStatus.FAILED.value,
            "error": "Missing project for render",
            "render_pack": None,
        }
    job = state.get("job") or {}
    try:
        result = RenderAgent().run(
            project,
            project_dir=state.get("project_dir"),
            config=job.get("config"),
            features=job.get("features"),
            clips=state.get("clips"),
            captions_pack=state.get("captions_pack"),
            reframe_pack=state.get("reframe_pack"),
            voice_pack=state.get("voice_pack"),
            music_pack=state.get("music_pack"),
            avatar_pack=state.get("avatar_pack"),
            platform_pack=state.get("platform_pack"),
            source_metadata=state.get("source_metadata"),
            speech_transcript=state.get("speech_transcript"),
        )
    except RenderAgentError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=13,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[render] Failed: {exc}")
        return {
            "current_step": 14,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "render_pack": None,
        }
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "current_step": 13,
        "steps": _step14_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_render(state: WorkflowState) -> str:
    if state.get("status") == JobStatus.FAILED.value or state.get("error"):
        return "render_failed"
    return "continue"


def _render_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Render failed",
    }


def _quality_node(state: WorkflowState) -> dict[str, Any]:
    """Quality Agent: validate/correct; may request one re-render."""
    project = state.get("project")
    if not project:
        return {
            "status": JobStatus.FAILED.value,
            "error": "Missing project for quality checks",
            "quality_pack": None,
        }
    job = state.get("job") or {}
    retry_count = int(state.get("quality_retry_count") or 0)
    try:
        result = QualityAgent().run(
            project,
            project_dir=state.get("project_dir"),
            config=job.get("config"),
            features=job.get("features"),
            render_pack=state.get("render_pack"),
            platform_pack=state.get("platform_pack"),
            captions_pack=state.get("captions_pack"),
            quality_retry_count=retry_count,
        )
    except QualityAgentError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=13,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[quality] Failed: {exc}")
        return {
            "current_step": 14,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "quality_pack": None,
        }
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    return {
        **result.to_state_dict(),
        "current_step": 13,
        "steps": _step14_running(state),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _route_after_quality(state: WorkflowState) -> str:
    if state.get("status") == JobStatus.FAILED.value or state.get("error"):
        return "quality_failed"
    pack = state.get("quality_pack") or {}
    report = pack.get("report") if isinstance(pack, dict) else None
    if isinstance(report, dict):
        if report.get("rerender_requested") and int(
            state.get("quality_retry_count") or 0
        ) < 1:
            return "retry"
        if report.get("passed") is False and not report.get("skipped"):
            return "quality_failed"
    return "continue"


def _quality_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Quality validation failed",
    }


def _quality_retry_bump(state: WorkflowState) -> dict[str, Any]:
    """Increment retry count before looping back to render."""
    count = int(state.get("quality_retry_count") or 0) + 1
    messages = list(state.get("messages") or [])
    messages.append(f"[quality] Re-render requested (attempt {count})")
    return {
        "quality_retry_count": count,
        "messages": messages,
        "steps": _step14_running(state),
        "status": JobStatus.RUNNING.value,
        "error": None,
    }


def _export_node(state: WorkflowState) -> dict[str, Any]:
    """Export Agent: package deliverables; completes step 14 and the job."""
    project = state.get("project")
    if not project:
        return {
            "status": JobStatus.FAILED.value,
            "error": "Missing project for export",
            "export_pack": None,
        }
    job = state.get("job") or {}
    try:
        result = ExportAgent().run(
            project,
            project_dir=state.get("project_dir"),
            config=job.get("config"),
            features=job.get("features"),
            render_pack=state.get("render_pack"),
            quality_pack=state.get("quality_pack"),
            captions_pack=state.get("captions_pack"),
            platform_pack=state.get("platform_pack"),
            workflow_state=dict(state),
        )
    except ExportAgentError as exc:
        steps = _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=13,
        )
        messages = list(state.get("messages") or [])
        messages.append(f"[export] Failed: {exc}")
        return {
            "current_step": 14,
            "steps": steps,
            "messages": messages,
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "export_pack": None,
        }
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    export_path = result.export_pack.export_path
    merged = dict(state)
    merged.update(result.to_state_dict())
    merged["status"] = JobStatus.COMPLETED.value
    merged["error"] = None
    flat = project_state_view(merged)
    project = state.get("project") or {}
    result_payload = {
        "job_id": job.get("job_id"),
        "project_id": project.get("project_id") or job.get("job_id"),
        "source_type": job.get("source_type"),
        "project_dir": state.get("project_dir"),
        "source_dir": state.get("source_dir"),
        "source_metadata": state.get("source_metadata"),
        "transcript": state.get("transcript"),
        "speech_transcript": state.get("speech_transcript"),
        "analysis": state.get("analysis"),
        "scenes": state.get("scenes"),
        "audio_analysis": state.get("audio_analysis"),
        "speakers": state.get("speakers"),
        "moments": state.get("moments"),
        "clips": state.get("clips"),
        "video_type_pack": state.get("video_type_pack"),
        "visual_style_pack": state.get("visual_style_pack"),
        "environment_pack": state.get("environment_pack"),
        "stories": state.get("stories"),
        "scripts": state.get("scripts"),
        "localizations": state.get("localizations"),
        "cultural_adaptation": state.get("cultural_adaptation"),
        "humor_localization": state.get("humor_localization"),
        "broll_pack": state.get("broll_pack"),
        "voice_pack": state.get("voice_pack"),
        "music_pack": state.get("music_pack"),
        "captions_pack": state.get("captions_pack"),
        "reframe_pack": state.get("reframe_pack"),
        "platform_pack": state.get("platform_pack"),
        "render_pack": state.get("render_pack"),
        "quality_pack": state.get("quality_pack"),
        "export_pack": result.export_pack.model_dump(mode="json"),
        "export_path": export_path,
        "output_files": flat.get("output_files") or {},
        "detail": (
            "Pipeline finished — export package ready; "
            "opening platform URLs is not publishing."
        ),
        **{k: flat[k] for k in (
            "duration",
            "video_path",
            "selected_clips",
            "story",
            "script",
            "country",
            "region",
            "language",
            "cultural_context",
            "humor_context",
            "render_plan",
            "quality_report",
            "errors",
            "progress",
        ) if k in flat},
    }
    return {
        **result.to_state_dict(),
        "current_step": 14,
        "steps": _mark_steps_completed(
            state.get("steps", initial_progress_steps()),
            completed_through=14,
        ),
        "messages": messages,
        "status": JobStatus.COMPLETED.value,
        "error": None,
        "result": result_payload,
    }


def _route_after_export(state: WorkflowState) -> str:
    if state.get("status") == JobStatus.FAILED.value or state.get("error"):
        return "export_failed"
    return "continue"


def _export_failed_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "status": JobStatus.FAILED.value,
        "error": state.get("error") or "Export packaging failed",
    }


def build_flat_video_graph(checkpointer=None):
    """Build the flat agent StateGraph (all nodes/edges preserved)."""
    graph = StateGraph(WorkflowState)

    graph.add_node("input_agent", _input_agent_node)
    graph.add_node("input_failed", _input_failed_node)
    graph.add_node("youtube_ingest", _youtube_ingest_node)
    graph.add_node("youtube_failed", _youtube_failed_node)
    graph.add_node("local_video_ingest", _local_video_ingest_node)
    graph.add_node("local_video_failed", _local_video_failed_node)
    graph.add_node("script_ingest", _script_ingest_node)
    graph.add_node("script_failed", _script_failed_node)
    graph.add_node(TRANSCRIPT_NODE, _transcript_extract_node)
    graph.add_node("transcript_failed", _transcript_failed_node)
    graph.add_node(UNDERSTANDING_NODE, _video_understanding_node)
    graph.add_node("understanding_failed", _understanding_failed_node)
    graph.add_node(SCENE_DETECTION_NODE, _scene_detection_node)
    graph.add_node("scene_detection_failed", _scene_detection_failed_node)
    graph.add_node(AUDIO_ANALYSIS_NODE, _audio_analysis_node)
    graph.add_node("audio_analysis_failed", _audio_analysis_failed_node)
    graph.add_node(SPEAKER_ANALYSIS_NODE, _speaker_analysis_node)
    graph.add_node("speaker_analysis_failed", _speaker_analysis_failed_node)
    graph.add_node(FUNNY_MOMENT_NODE, _funny_moment_node)
    graph.add_node("funny_moment_failed", _funny_moment_failed_node)
    graph.add_node(VIRAL_MOMENT_NODE, _viral_moment_node)
    graph.add_node("viral_moment_failed", _viral_moment_failed_node)
    graph.add_node(MOMENT_DETECTION_NODE, _moment_detection_node)
    graph.add_node("moment_detection_failed", _moment_detection_failed_node)
    graph.add_node(SMART_CLIP_NODE, _smart_clip_node)
    graph.add_node("smart_clip_failed", _smart_clip_failed_node)
    graph.add_node(PODCAST_NODE, _podcast_node)
    graph.add_node("podcast_failed", _podcast_failed_node)
    graph.add_node(RESEARCH_NODE, _research_node)
    graph.add_node("research_failed", _research_failed_node)
    graph.add_node(SHARED_AI_NODE, _shared_ai_analysis_node)
    graph.add_node(OBJECT_DETECTION_NODE, _object_detection_node)
    graph.add_node(SUPERVISOR_NODE, _supervisor_node)
    graph.add_node("crew_failed", _crew_failed_node)
    graph.add_node("crew_research", _crew_worker_research_node)
    graph.add_node("crew_story", _crew_worker_story_node)
    graph.add_node("crew_script", _crew_worker_script_node)
    graph.add_node("crew_director", _crew_worker_director_node)
    graph.add_node("crew_video_generation", _crew_worker_video_generation_node)
    graph.add_node("crew_captions", _crew_worker_captions_node)
    graph.add_node("crew_thumbnail", _crew_worker_thumbnail_node)
    graph.add_node("crew_seo", _crew_worker_seo_node)
    graph.add_node(VIDEO_TYPE_NODE, _video_type_node)
    graph.add_node("video_type_failed", _video_type_failed_node)
    graph.add_node(VISUAL_STYLE_NODE, _visual_style_node)
    graph.add_node("visual_style_failed", _visual_style_failed_node)
    graph.add_node(ENVIRONMENT_NODE, _environment_node)
    graph.add_node("environment_failed", _environment_failed_node)
    graph.add_node(STORY_NODE, _story_node)
    graph.add_node("story_failed", _story_failed_node)
    graph.add_node(SCRIPT_NODE, _script_node)
    graph.add_node("script_gen_failed", _script_gen_failed_node)
    graph.add_node(COUNTRY_NODE, _country_node)
    graph.add_node("country_failed", _country_failed_node)
    graph.add_node(REGIONAL_NODE, _regional_node)
    graph.add_node("regional_failed", _regional_failed_node)
    graph.add_node(CULTURAL_NODE, _cultural_node)
    graph.add_node("cultural_failed", _cultural_failed_node)
    graph.add_node(HUMOR_NODE, _humor_node)
    graph.add_node("humor_failed", _humor_failed_node)
    graph.add_node(LANGUAGE_NODE, _language_node)
    graph.add_node("language_failed", _language_failed_node)
    graph.add_node(STORYBOARD_NODE, _storyboard_node)
    graph.add_node("storyboard_failed", _storyboard_failed_node)
    graph.add_node(CHARACTER_NODE, _character_node)
    graph.add_node("character_failed", _character_failed_node)
    graph.add_node(CAMERA_NODE, _camera_node)
    graph.add_node("camera_failed", _camera_failed_node)
    graph.add_node(DIRECTOR_NODE, _director_node)
    graph.add_node("director_failed", _director_failed_node)
    graph.add_node(MOTION_GRAPHICS_NODE, _motion_graphics_node)
    graph.add_node("motion_graphics_failed", _motion_graphics_failed_node)
    graph.add_node(DOCUMENTARY_NODE, _documentary_node)
    graph.add_node("documentary_failed", _documentary_failed_node)
    graph.add_node(VIDEO_GENERATION_NODE, _video_generation_node)
    graph.add_node("video_generation_failed", _video_generation_failed_node)
    graph.add_node(IMAGE_GENERATION_NODE, _image_generation_node)
    graph.add_node("image_generation_failed", _image_generation_failed_node)
    graph.add_node(BROLL_NODE, _broll_node)
    graph.add_node("b_roll_failed", _broll_failed_node)
    graph.add_node(VOICE_NODE, _voice_node)
    graph.add_node("voice_failed", _voice_failed_node)
    graph.add_node(AVATAR_NODE, _avatar_node)
    graph.add_node("avatar_failed", _avatar_failed_node)
    graph.add_node(MUSIC_NODE, _music_node)
    graph.add_node("music_failed", _music_failed_node)
    graph.add_node(CAPTIONS_NODE, _captions_node)
    graph.add_node("captions_failed", _captions_failed_node)
    graph.add_node(REFRAME_NODE, _reframe_node)
    graph.add_node("reframe_failed", _reframe_failed_node)
    graph.add_node(PLATFORM_NODE, _platform_node)
    graph.add_node("platform_failed", _platform_failed_node)
    graph.add_node(BRAND_NODE, _brand_node)
    graph.add_node("brand_failed", _brand_failed_node)
    graph.add_node(SEO_NODE, _seo_node)
    graph.add_node("seo_failed", _seo_failed_node)
    graph.add_node(TREND_NODE, _trend_node)
    graph.add_node("trend_failed", _trend_failed_node)
    graph.add_node(COMPETITOR_NODE, _competitor_node)
    graph.add_node(REPURPOSE_NODE, _repurpose_node)
    graph.add_node("repurpose_failed", _repurpose_failed_node)
    graph.add_node(CALENDAR_NODE, _calendar_node)
    graph.add_node("calendar_failed", _calendar_failed_node)
    graph.add_node(THUMBNAIL_NODE, _thumbnail_node)
    graph.add_node("thumbnail_failed", _thumbnail_failed_node)
    graph.add_node(ANALYTICS_NODE, _analytics_node)
    graph.add_node("analytics_failed", _analytics_failed_node)
    graph.add_node(RENDER_NODE, _render_node)
    graph.add_node("render_failed", _render_failed_node)
    graph.add_node(QUALITY_NODE, _quality_node)
    graph.add_node("quality_failed", _quality_failed_node)
    graph.add_node("quality_retry", _quality_retry_bump)
    graph.add_node(EXPORT_NODE, _export_node)
    graph.add_node("export_failed", _export_failed_node)
    graph.add_node("skip_funny", _skip_funny_node)
    graph.add_node("skip_viral", _skip_viral_node)
    graph.add_node("skip_podcast", _skip_podcast_node)
    graph.add_node("skip_research", _skip_research_node)
    graph.add_node("skip_cultural", _skip_cultural_node)
    graph.add_node("skip_humor", _skip_humor_node)
    graph.add_node("skip_broll", _skip_broll_node)
    graph.add_node("skip_storyboard", _skip_storyboard_node)
    graph.add_node("skip_character", _skip_character_node)
    graph.add_node("skip_camera", _skip_camera_node)
    graph.add_node("skip_director", _skip_director_node)
    graph.add_node("skip_motion_graphics", _skip_motion_graphics_node)
    graph.add_node("skip_documentary", _skip_documentary_node)
    graph.add_node("skip_video_generation", _skip_video_generation_node)
    graph.add_node("skip_image_generation", _skip_image_generation_node)
    graph.add_node("skip_voice", _skip_voice_node)
    graph.add_node("skip_avatar", _skip_avatar_node)
    graph.add_node("skip_music", _skip_music_node)
    graph.add_node("skip_seo", _skip_seo_node)
    graph.add_node("skip_brand", _skip_brand_node)
    graph.add_node("skip_trend", _skip_trend_node)
    graph.add_node("skip_repurpose", _skip_repurpose_node)
    graph.add_node("skip_calendar", _skip_calendar_node)
    graph.add_node("skip_thumbnail", _skip_thumbnail_node)
    graph.add_node("skip_analytics", _skip_analytics_node)

    graph.add_edge(START, "input_agent")
    graph.add_conditional_edges(
        "input_agent",
        _route_after_input,
        {
            "youtube_ingest": "youtube_ingest",
            "local_video_ingest": "local_video_ingest",
            "script_ingest": "script_ingest",
            "input_failed": "input_failed",
        },
    )
    graph.add_edge("input_failed", END)
    graph.add_edge("youtube_failed", END)
    graph.add_edge("script_failed", END)
    graph.add_edge("transcript_failed", END)
    graph.add_edge("understanding_failed", END)
    graph.add_edge("scene_detection_failed", END)
    graph.add_edge("audio_analysis_failed", END)
    graph.add_edge("speaker_analysis_failed", END)
    graph.add_edge("funny_moment_failed", END)
    graph.add_edge("viral_moment_failed", END)
    graph.add_edge("moment_detection_failed", END)
    graph.add_edge("smart_clip_failed", END)
    graph.add_edge("podcast_failed", END)
    graph.add_edge("research_failed", END)
    graph.add_edge("crew_failed", END)
    graph.add_edge("video_type_failed", END)
    graph.add_edge("visual_style_failed", END)
    graph.add_edge("environment_failed", END)
    graph.add_edge("story_failed", END)
    graph.add_edge("script_gen_failed", END)
    graph.add_edge("country_failed", END)
    graph.add_edge("regional_failed", END)
    graph.add_edge("cultural_failed", END)
    graph.add_edge("humor_failed", END)
    graph.add_edge("language_failed", END)
    graph.add_edge("storyboard_failed", END)
    graph.add_edge("character_failed", END)
    graph.add_edge("camera_failed", END)
    graph.add_edge("director_failed", END)
    graph.add_edge("motion_graphics_failed", END)
    graph.add_edge("documentary_failed", END)
    graph.add_edge("video_generation_failed", END)
    graph.add_edge("image_generation_failed", END)
    graph.add_edge("b_roll_failed", END)
    graph.add_edge("voice_failed", END)
    graph.add_edge("avatar_failed", END)
    graph.add_edge("music_failed", END)
    graph.add_edge("captions_failed", END)
    graph.add_edge("reframe_failed", END)
    graph.add_edge("platform_failed", END)
    graph.add_edge("brand_failed", END)
    graph.add_edge("seo_failed", END)
    graph.add_edge("trend_failed", END)
    graph.add_edge("repurpose_failed", END)
    graph.add_edge("calendar_failed", END)
    graph.add_edge("thumbnail_failed", END)
    graph.add_edge("analytics_failed", END)
    graph.add_edge("render_failed", END)
    graph.add_edge("quality_failed", END)
    graph.add_edge("export_failed", END)

    graph.add_conditional_edges(
        "youtube_ingest",
        _route_after_youtube,
        {
            "continue": TRANSCRIPT_NODE,
            "youtube_failed": "youtube_failed",
        },
    )
    graph.add_conditional_edges(
        "local_video_ingest",
        _route_after_local_video,
        {
            "continue": TRANSCRIPT_NODE,
            "local_video_failed": "local_video_failed",
        },
    )
    graph.add_edge("local_video_failed", END)
    graph.add_conditional_edges(
        TRANSCRIPT_NODE,
        _route_after_transcript,
        {
            "continue": UNDERSTANDING_NODE,
            "transcript_failed": "transcript_failed",
        },
    )
    graph.add_conditional_edges(
        "script_ingest",
        _route_after_script,
        {
            "continue": UNDERSTANDING_NODE,
            "script_failed": "script_failed",
        },
    )
    graph.add_conditional_edges(
        UNDERSTANDING_NODE,
        _route_after_understanding,
        {
            "continue": SCENE_DETECTION_NODE,
            "understanding_failed": "understanding_failed",
        },
    )
    graph.add_conditional_edges(
        SCENE_DETECTION_NODE,
        _route_after_scene_detection,
        {
            "continue": AUDIO_ANALYSIS_NODE,
            "scene_detection_failed": "scene_detection_failed",
        },
    )
    graph.add_conditional_edges(
        AUDIO_ANALYSIS_NODE,
        _route_after_audio_analysis,
        {
            "continue": SPEAKER_ANALYSIS_NODE,
            "audio_analysis_failed": "audio_analysis_failed",
        },
    )
    graph.add_conditional_edges(
        SPEAKER_ANALYSIS_NODE,
        _route_after_speaker_analysis,
        {
            "continue": MOMENT_DETECTION_NODE,
            "speaker_analysis_failed": "speaker_analysis_failed",
        },
    )
    graph.add_conditional_edges(
        MOMENT_DETECTION_NODE,
        _route_after_moment_detection,
        {
            "funny": FUNNY_MOMENT_NODE,
            "skip_funny": "skip_funny",
            "moment_detection_failed": "moment_detection_failed",
        },
    )
    graph.add_conditional_edges(
        FUNNY_MOMENT_NODE,
        _route_after_funny_moment,
        {
            "viral": VIRAL_MOMENT_NODE,
            "skip_viral": "skip_viral",
            "funny_moment_failed": "funny_moment_failed",
        },
    )
    graph.add_conditional_edges(
        "skip_funny",
        _route_after_funny_moment,
        {
            "viral": VIRAL_MOMENT_NODE,
            "skip_viral": "skip_viral",
            "funny_moment_failed": "funny_moment_failed",
        },
    )
    graph.add_conditional_edges(
        VIRAL_MOMENT_NODE,
        _route_after_viral_moment,
        {
            "continue": SMART_CLIP_NODE,
            "viral_moment_failed": "viral_moment_failed",
        },
    )
    graph.add_edge("skip_viral", SMART_CLIP_NODE)
    graph.add_conditional_edges(
        SMART_CLIP_NODE,
        _route_after_smart_clip,
        {
            "podcast": PODCAST_NODE,
            "skip_podcast": "skip_podcast",
            "smart_clip_failed": "smart_clip_failed",
        },
    )
    graph.add_conditional_edges(
        PODCAST_NODE,
        _route_after_podcast,
        {
            "research": RESEARCH_NODE,
            "skip_research": "skip_research",
            "podcast_failed": "podcast_failed",
        },
    )
    graph.add_conditional_edges(
        "skip_podcast",
        _route_after_podcast,
        {
            "research": RESEARCH_NODE,
            "skip_research": "skip_research",
            "podcast_failed": "podcast_failed",
        },
    )
    graph.add_conditional_edges(
        RESEARCH_NODE,
        _route_after_research,
        {
            "supervisor": SHARED_AI_NODE,
            "story": SHARED_AI_NODE,
            "research_failed": "research_failed",
        },
    )
    graph.add_conditional_edges(
        "skip_research",
        _route_after_research,
        {
            "supervisor": SHARED_AI_NODE,
            "story": SHARED_AI_NODE,
            "research_failed": "research_failed",
        },
    )
    graph.add_edge(SHARED_AI_NODE, OBJECT_DETECTION_NODE)
    graph.add_conditional_edges(
        OBJECT_DETECTION_NODE,
        _route_after_objects,
        {
            "supervisor": SUPERVISOR_NODE,
            "story": STORY_NODE,
            "research_failed": "research_failed",
        },
    )
    graph.add_conditional_edges(
        SUPERVISOR_NODE,
        _route_after_supervisor,
        {
            "research": "crew_research",
            "story": "crew_story",
            "script": "crew_script",
            "director": "crew_director",
            "video_generation": "crew_video_generation",
            "captions": "crew_captions",
            "thumbnail": "crew_thumbnail",
            "seo": "crew_seo",
            "FINISH": COUNTRY_NODE,
            "crew_failed": "crew_failed",
        },
    )
    for _crew_worker in (
        "crew_research",
        "crew_story",
        "crew_script",
        "crew_director",
        "crew_video_generation",
        "crew_captions",
        "crew_thumbnail",
        "crew_seo",
    ):
        graph.add_edge(_crew_worker, SUPERVISOR_NODE)
    graph.add_conditional_edges(
        STORY_NODE,
        _route_after_story,
        {
            "continue": SCRIPT_NODE,
            "story_failed": "story_failed",
        },
    )
    graph.add_conditional_edges(
        SCRIPT_NODE,
        _route_after_script_gen,
        {
            "continue": COUNTRY_NODE,
            "script_gen_failed": "script_gen_failed",
        },
    )
    graph.add_conditional_edges(
        COUNTRY_NODE,
        _route_after_country,
        {
            "continue": REGIONAL_NODE,
            "country_failed": "country_failed",
        },
    )
    graph.add_conditional_edges(
        REGIONAL_NODE,
        _route_after_regional,
        {
            "language": LANGUAGE_NODE,
            "regional_failed": "regional_failed",
        },
    )
    graph.add_conditional_edges(
        LANGUAGE_NODE,
        _route_after_language,
        {
            "cultural": CULTURAL_NODE,
            "skip_cultural": "skip_cultural",
            "language_failed": "language_failed",
        },
    )
    graph.add_conditional_edges(
        CULTURAL_NODE,
        _route_after_cultural,
        {
            "humor": HUMOR_NODE,
            "skip_humor": "skip_humor",
            "cultural_failed": "cultural_failed",
        },
    )
    graph.add_conditional_edges(
        "skip_cultural",
        _route_after_cultural,
        {
            "humor": HUMOR_NODE,
            "skip_humor": "skip_humor",
            "cultural_failed": "cultural_failed",
        },
    )
    graph.add_conditional_edges(
        HUMOR_NODE,
        _route_after_humor,
        {
            "continue": VIDEO_TYPE_NODE,
            "humor_failed": "humor_failed",
        },
    )
    graph.add_edge("skip_humor", VIDEO_TYPE_NODE)
    graph.add_conditional_edges(
        VIDEO_TYPE_NODE,
        _route_after_video_type,
        {
            "continue": VISUAL_STYLE_NODE,
            "video_type_failed": "video_type_failed",
        },
    )
    graph.add_conditional_edges(
        VISUAL_STYLE_NODE,
        _route_after_visual_style,
        {
            "continue": ENVIRONMENT_NODE,
            "visual_style_failed": "visual_style_failed",
        },
    )
    graph.add_conditional_edges(
        ENVIRONMENT_NODE,
        _route_after_environment,
        {
            "storyboard": STORYBOARD_NODE,
            "skip_storyboard": "skip_storyboard",
            "environment_failed": "environment_failed",
        },
    )
    graph.add_conditional_edges(
        STORYBOARD_NODE,
        _route_after_storyboard,
        {
            "character": CHARACTER_NODE,
            "skip_character": "skip_character",
            "storyboard_failed": "storyboard_failed",
        },
    )
    graph.add_conditional_edges(
        "skip_storyboard",
        _route_after_storyboard,
        {
            "character": CHARACTER_NODE,
            "skip_character": "skip_character",
            "storyboard_failed": "storyboard_failed",
        },
    )
    graph.add_conditional_edges(
        CHARACTER_NODE,
        _route_after_character,
        {
            "camera": CAMERA_NODE,
            "skip_camera": "skip_camera",
            "character_failed": "character_failed",
        },
    )
    graph.add_conditional_edges(
        "skip_character",
        _route_after_character,
        {
            "camera": CAMERA_NODE,
            "skip_camera": "skip_camera",
            "character_failed": "character_failed",
        },
    )
    graph.add_conditional_edges(
        CAMERA_NODE,
        _route_after_camera,
        {
            "director": DIRECTOR_NODE,
            "skip_director": "skip_director",
            "camera_failed": "camera_failed",
        },
    )
    graph.add_conditional_edges(
        "skip_camera",
        _route_after_camera,
        {
            "director": DIRECTOR_NODE,
            "skip_director": "skip_director",
            "camera_failed": "camera_failed",
        },
    )
    graph.add_conditional_edges(
        DIRECTOR_NODE,
        _route_after_director,
        {
            "motion_graphics": MOTION_GRAPHICS_NODE,
            "skip_motion_graphics": "skip_motion_graphics",
            "director_failed": "director_failed",
        },
    )
    graph.add_conditional_edges(
        "skip_director",
        _route_after_director,
        {
            "motion_graphics": MOTION_GRAPHICS_NODE,
            "skip_motion_graphics": "skip_motion_graphics",
            "director_failed": "director_failed",
        },
    )
    graph.add_conditional_edges(
        MOTION_GRAPHICS_NODE,
        _route_after_motion_graphics,
        {
            "documentary": DOCUMENTARY_NODE,
            "skip_documentary": "skip_documentary",
            "motion_graphics_failed": "motion_graphics_failed",
        },
    )
    graph.add_conditional_edges(
        "skip_motion_graphics",
        _route_after_motion_graphics,
        {
            "documentary": DOCUMENTARY_NODE,
            "skip_documentary": "skip_documentary",
            "motion_graphics_failed": "motion_graphics_failed",
        },
    )
    graph.add_conditional_edges(
        DOCUMENTARY_NODE,
        _route_after_documentary,
        {
            "video_generation": VIDEO_GENERATION_NODE,
            "skip_video_generation": "skip_video_generation",
            "documentary_failed": "documentary_failed",
        },
    )
    graph.add_conditional_edges(
        "skip_documentary",
        _route_after_documentary,
        {
            "video_generation": VIDEO_GENERATION_NODE,
            "skip_video_generation": "skip_video_generation",
            "documentary_failed": "documentary_failed",
        },
    )
    graph.add_conditional_edges(
        VIDEO_GENERATION_NODE,
        _route_after_video_generation,
        {
            "image_generation": IMAGE_GENERATION_NODE,
            "skip_image_generation": "skip_image_generation",
            "video_generation_failed": "video_generation_failed",
        },
    )
    graph.add_conditional_edges(
        "skip_video_generation",
        _route_after_video_generation,
        {
            "image_generation": IMAGE_GENERATION_NODE,
            "skip_image_generation": "skip_image_generation",
            "video_generation_failed": "video_generation_failed",
        },
    )
    graph.add_conditional_edges(
        IMAGE_GENERATION_NODE,
        _route_after_image_generation,
        {
            "b_roll": BROLL_NODE,
            "skip_broll": "skip_broll",
            "image_generation_failed": "image_generation_failed",
        },
    )
    graph.add_conditional_edges(
        "skip_image_generation",
        _route_after_image_generation,
        {
            "b_roll": BROLL_NODE,
            "skip_broll": "skip_broll",
            "image_generation_failed": "image_generation_failed",
        },
    )
    graph.add_conditional_edges(
        BROLL_NODE,
        _route_after_broll,
        {
            "voice": VOICE_NODE,
            "skip_voice": "skip_voice",
            "b_roll_failed": "b_roll_failed",
        },
    )
    graph.add_conditional_edges(
        "skip_broll",
        _route_after_broll,
        {
            "voice": VOICE_NODE,
            "skip_voice": "skip_voice",
            "b_roll_failed": "b_roll_failed",
        },
    )
    graph.add_conditional_edges(
        VOICE_NODE,
        _route_after_voice,
        {
            "avatar": AVATAR_NODE,
            "skip_avatar": "skip_avatar",
            "voice_failed": "voice_failed",
        },
    )
    graph.add_conditional_edges(
        "skip_voice",
        _route_after_voice,
        {
            "avatar": AVATAR_NODE,
            "skip_avatar": "skip_avatar",
            "voice_failed": "voice_failed",
        },
    )
    graph.add_conditional_edges(
        AVATAR_NODE,
        _route_after_avatar,
        {
            "music": MUSIC_NODE,
            "skip_music": "skip_music",
            "avatar_failed": "avatar_failed",
        },
    )
    graph.add_conditional_edges(
        "skip_avatar",
        _route_after_avatar,
        {
            "music": MUSIC_NODE,
            "skip_music": "skip_music",
            "avatar_failed": "avatar_failed",
        },
    )
    graph.add_conditional_edges(
        MUSIC_NODE,
        _route_after_music,
        {
            "continue": CAPTIONS_NODE,
            "music_failed": "music_failed",
        },
    )
    graph.add_edge("skip_music", CAPTIONS_NODE)
    graph.add_conditional_edges(
        CAPTIONS_NODE,
        _route_after_captions,
        {
            "continue": REFRAME_NODE,
            "captions_failed": "captions_failed",
        },
    )
    graph.add_conditional_edges(
        REFRAME_NODE,
        _route_after_reframe,
        {
            "continue": PLATFORM_NODE,
            "reframe_failed": "reframe_failed",
        },
    )
    graph.add_conditional_edges(
        PLATFORM_NODE,
        _route_after_platform,
        {
            "brand": BRAND_NODE,
            "skip_brand": "skip_brand",
            "platform_failed": "platform_failed",
        },
    )
    graph.add_conditional_edges(
        BRAND_NODE,
        _route_after_brand,
        {
            "seo": SEO_NODE,
            "skip_seo": "skip_seo",
            "brand_failed": "brand_failed",
        },
    )
    graph.add_conditional_edges(
        "skip_brand",
        _route_after_brand,
        {
            "seo": SEO_NODE,
            "skip_seo": "skip_seo",
            "brand_failed": "brand_failed",
        },
    )
    graph.add_conditional_edges(
        SEO_NODE,
        _route_after_seo,
        {
            "trend": TREND_NODE,
            "skip_trend": "skip_trend",
            "seo_failed": "seo_failed",
        },
    )
    graph.add_conditional_edges(
        "skip_seo",
        _route_after_seo,
        {
            "trend": TREND_NODE,
            "skip_trend": "skip_trend",
            "seo_failed": "seo_failed",
        },
    )
    graph.add_conditional_edges(
        TREND_NODE,
        _route_after_trend,
        {
            "repurpose": COMPETITOR_NODE,
            "skip_repurpose": COMPETITOR_NODE,
            "trend_failed": "trend_failed",
        },
    )
    graph.add_conditional_edges(
        "skip_trend",
        _route_after_trend,
        {
            "repurpose": COMPETITOR_NODE,
            "skip_repurpose": COMPETITOR_NODE,
            "trend_failed": "trend_failed",
        },
    )
    graph.add_conditional_edges(
        COMPETITOR_NODE,
        _route_after_competitor,
        {
            "repurpose": REPURPOSE_NODE,
            "skip_repurpose": "skip_repurpose",
            "trend_failed": "trend_failed",
        },
    )
    graph.add_conditional_edges(
        REPURPOSE_NODE,
        _route_after_repurpose,
        {
            "content_calendar": CALENDAR_NODE,
            "skip_calendar": "skip_calendar",
            "repurpose_failed": "repurpose_failed",
        },
    )
    graph.add_conditional_edges(
        "skip_repurpose",
        _route_after_repurpose,
        {
            "content_calendar": CALENDAR_NODE,
            "skip_calendar": "skip_calendar",
            "repurpose_failed": "repurpose_failed",
        },
    )
    graph.add_conditional_edges(
        CALENDAR_NODE,
        _route_after_calendar,
        {
            "thumbnail": THUMBNAIL_NODE,
            "skip_thumbnail": "skip_thumbnail",
            "calendar_failed": "calendar_failed",
        },
    )
    graph.add_conditional_edges(
        "skip_calendar",
        _route_after_calendar,
        {
            "thumbnail": THUMBNAIL_NODE,
            "skip_thumbnail": "skip_thumbnail",
            "calendar_failed": "calendar_failed",
        },
    )
    graph.add_conditional_edges(
        THUMBNAIL_NODE,
        _route_after_thumbnail,
        {
            "analytics": ANALYTICS_NODE,
            "skip_analytics": "skip_analytics",
            "thumbnail_failed": "thumbnail_failed",
        },
    )
    graph.add_conditional_edges(
        "skip_thumbnail",
        _route_after_thumbnail,
        {
            "analytics": ANALYTICS_NODE,
            "skip_analytics": "skip_analytics",
            "thumbnail_failed": "thumbnail_failed",
        },
    )
    graph.add_conditional_edges(
        ANALYTICS_NODE,
        _route_after_analytics,
        {
            "continue": RENDER_NODE,
            "analytics_failed": "analytics_failed",
        },
    )
    graph.add_edge("skip_analytics", RENDER_NODE)
    graph.add_conditional_edges(
        RENDER_NODE,
        _route_after_render,
        {
            "continue": QUALITY_NODE,
            "render_failed": "render_failed",
        },
    )
    graph.add_conditional_edges(
        QUALITY_NODE,
        _route_after_quality,
        {
            "continue": EXPORT_NODE,
            "retry": "quality_retry",
            "quality_failed": "quality_failed",
        },
    )
    graph.add_edge("quality_retry", RENDER_NODE)
    graph.add_conditional_edges(
        EXPORT_NODE,
        _route_after_export,
        {
            "continue": END,
            "export_failed": "export_failed",
        },
    )

    return graph.compile(checkpointer=checkpointer)


def build_video_graph(checkpointer=None):
    """Public API: nested MainGraph when USE_NESTED_GRAPH, else flat agents."""
    try:
        from config.settings import get_settings

        nested = bool(get_settings().use_nested_graph)
    except Exception:  # noqa: BLE001
        nested = False
    if nested:
        from graph.main import build_main_graph

        return build_main_graph(checkpointer=checkpointer)
    return build_flat_video_graph(checkpointer=checkpointer)


def build_graph(checkpointer=None):
    """Alias used by tests and package exports."""
    return build_video_graph(checkpointer=checkpointer)


def _initial_state(request: VideoJobRequest) -> WorkflowState:
    return {
        "job": request.model_dump(mode="json"),
        "status": JobStatus.RUNNING.value,
        "current_step": -1,
        "steps": initial_progress_steps(),
        "messages": [],
        "error": None,
        "result": None,
        "project": None,
        "project_dir": None,
        "next_agent": None,
        "source_metadata": None,
        "source_dir": None,
        "transcript": None,
        "speech_transcript": None,
        "analysis": None,
        "scenes": None,
        "audio_analysis": None,
        "speakers": None,
        "funny_moments": None,
        "viral_moments": None,
        "moments": None,
        "clips": None,
        "podcast_clips": None,
        "research_report": None,
        "supervisor_crew": None,
        "delegation_log": [],
        "task_board": [],
        "crew_retry_counts": {},
        "crew_step": 0,
        "video_type_pack": None,
        "visual_style_pack": None,
        "environment_pack": None,
        "storyboard_pack": None,
        "character_pack": None,
        "camera_pack": None,
        "director_pack": None,
        "motion_graphics_pack": None,
        "documentary_pack": None,
        "video_generation_pack": None,
        "stories": None,
        "scripts": None,
        "country_profile": None,
        "region_profile": None,
        "locale_pack": None,
        "cultural_adaptation": None,
        "humor_localization": None,
        "localizations": None,
        "image_pack": None,
        "broll_pack": None,
        "voice_pack": None,
        "avatar_pack": None,
        "music_pack": None,
        "captions_pack": None,
        "reframe_pack": None,
        "platform_pack": None,
        "brand_pack": None,
        "seo_pack": None,
        "trend_pack": None,
        "repurpose_pack": None,
        "calendar_pack": None,
        "thumbnail_pack": None,
        "analytics_pack": None,
        "render_pack": None,
        "quality_pack": None,
        "export_pack": None,
        "quality_retry_count": 0,
    }


def run_video_workflow(
    request: VideoJobRequest,
    on_step: OnStepCallback | None = None,
    *,
    resume: bool = False,
    from_step: str | None = None,
    project_id: str | None = None,
    retry_failed: bool = False,
    max_retries: int = 1,
    checkpointer: Any = None,
) -> dict[str, Any]:
    """Run the pipeline with optional checkpoint resume / partial rerun.

    Persistence: ``memory.json``, ``execution_history.jsonl``, and
    ``checkpoints.sqlite`` under ``outputs/projects/{project_id}/``.
    """
    from core.workflow_memory import (
        append_history,
        assert_compatible_version,
        clear_from_step,
        get_checkpointer,
        load_memory,
        new_memory,
        save_memory,
        update_from_workflow_state,
    )
    from graph.rehydrate import rehydrate_state_from_disk
    from graph.version import WORKFLOW_VERSION
    from schemas.memory import ExecutionHistoryEvent

    pid = (project_id or request.job_id or "").strip()
    if not pid:
        raise WorkflowError("project_id / job_id required for workflow memory")

    owned_conn = None
    cp = checkpointer
    try:
        if cp is None:
            cp, owned_conn = get_checkpointer(pid)

        compiled = build_video_graph(checkpointer=cp)
        config: dict[str, Any] = {"configurable": {"thread_id": pid}}

        memory = load_memory(pid)
        if resume or from_step or retry_failed:
            if memory is None:
                raise WorkflowError(
                    f"No memory.json for project {pid!r} — cannot resume/rerun."
                )
            assert_compatible_version(memory)

        if memory is None:
            memory = new_memory(
                pid, job=request.model_dump(mode="json")
            )
            memory.workflow_version = WORKFLOW_VERSION
            memory.status = JobStatus.RUNNING.value
            save_memory(memory)

        if retry_failed:
            retry_key = (
                (memory.failed_steps[0] if memory.failed_steps else None)
                or memory.last_node
                or "workflow"
            )
            count = int(memory.retry_counts.get(retry_key, 0))
            if count >= max_retries:
                raise WorkflowError(
                    f"Max retries ({max_retries}) exceeded for step {retry_key!r}"
                )
            memory.retry_counts[retry_key] = count + 1
            memory.failed_steps = []
            memory.error = None
            memory.status = JobStatus.RUNNING.value
            save_memory(memory)
            append_history(
                pid,
                ExecutionHistoryEvent(
                    node=memory.last_node or "retry",
                    event="resume",
                    detail=f"retry_failed counts={memory.retry_counts}",
                ),
            )
            resume = True

        # Decide input for stream
        snapshot = None
        try:
            snapshot = compiled.get_state(config)
        except Exception:  # noqa: BLE001
            snapshot = None

        has_checkpoint = bool(
            snapshot
            and getattr(snapshot, "values", None)
            and snapshot.values.get("project")
        )
        checkpoint_pending = bool(has_checkpoint and getattr(snapshot, "next", None))

        # Failed/finished threads cannot continue via stream(None); infer a node.
        if (
            (resume or retry_failed)
            and not from_step
            and has_checkpoint
            and not checkpoint_pending
            and memory.status != JobStatus.COMPLETED.value
        ):
            from core.workflow_memory import PIPELINE_NODE_ORDER

            failed_node = None
            if PIPELINE_STEPS[9] in memory.failed_steps:
                failed_node = "story"
            if failed_node:
                from_step = failed_node
            elif memory.last_node in PIPELINE_NODE_ORDER:
                from_step = memory.last_node
            else:
                last_idx = -1
                for i, name in enumerate(PIPELINE_NODE_ORDER):
                    if name in memory.timestamps:
                        last_idx = i
                if last_idx >= 0 and last_idx + 1 < len(PIPELINE_NODE_ORDER):
                    from_step = PIPELINE_NODE_ORDER[last_idx + 1]
                elif last_idx >= 0:
                    from_step = PIPELINE_NODE_ORDER[last_idx]
                else:
                    from_step = "input_agent"

        if from_step:
            memory = clear_from_step(memory, from_step)
            save_memory(memory)
            append_history(
                pid,
                ExecutionHistoryEvent(
                    node=from_step,
                    event="rerun",
                    detail=f"partial rerun from_step={from_step}",
                ),
            )

        stream_input: Any
        if resume and has_checkpoint and checkpoint_pending and not from_step:
            stream_input = None
            append_history(
                pid,
                ExecutionHistoryEvent(
                    node=memory.last_node or "checkpoint",
                    event="resume",
                    detail="Continuing from Sqlite checkpoint",
                ),
            )
            state = dict(snapshot.values)
        elif (
            resume
            and has_checkpoint
            and not checkpoint_pending
            and not from_step
            and memory.status == JobStatus.COMPLETED.value
        ):
            append_history(
                pid,
                ExecutionHistoryEvent(
                    node=memory.last_node or "checkpoint",
                    event="resume",
                    detail="Already completed — returning checkpoint state",
                ),
            )
            return dict(snapshot.values)
        else:
            state = dict(_initial_state(request))
            if (resume or from_step) and memory.project_dir:
                state = rehydrate_state_from_disk(state, memory.project_dir)
                if memory.job:
                    # Keep original job identity for resume
                    state["job"] = dict(memory.job)
                    state["job"]["job_id"] = pid
                if memory.project_dir:
                    state["project_dir"] = memory.project_dir
            # Clear terminal failure so downstream nodes can run again
            if resume or from_step:
                state["status"] = JobStatus.RUNNING.value
                state["error"] = None
            stream_input = state
            if from_step:
                # Best-effort: jump to node after updating state into checkpoint
                try:
                    compiled.update_state(config, state)
                    from langgraph.types import Command

                    stream_input = Command(goto=from_step)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "from_step Command(goto) unavailable (%s); "
                        "running full graph with rehydrated state",
                        exc,
                    )
                    stream_input = state

        if on_step is not None:
            on_step(dict(state))

        prev_status = state.get("status")
        try:
            for event in compiled.stream(
                stream_input, config, stream_mode="values"
            ):
                state = dict(event)
                steps = [dict(s) for s in state.get("steps", [])]
                current = state.get("current_step", -1)
                next_idx = current + 1
                if (
                    state.get("status") == JobStatus.RUNNING.value
                    and 0 <= next_idx < len(steps)
                    and steps[next_idx].get("status") == ProgressStepStatus.PENDING.value
                ):
                    steps[next_idx]["status"] = ProgressStepStatus.RUNNING.value
                    state["steps"] = steps

                # Persist memory + history
                try:
                    running_label = ""
                    for step in steps:
                        if step.get("status") == ProgressStepStatus.RUNNING.value:
                            running_label = str(step.get("label") or "")
                            break
                    mem = update_from_workflow_state(
                        state, last_node=running_label or str(state.get("current_step"))
                    )
                    event_name = "completed"
                    if state.get("status") == JobStatus.FAILED.value:
                        event_name = "failed"
                    elif state.get("status") == JobStatus.COMPLETED.value:
                        event_name = "completed"
                    elif prev_status != state.get("status"):
                        event_name = "progress"
                    append_history(
                        pid,
                        ExecutionHistoryEvent(
                            node=mem.last_node or mem.current_step,
                            event=event_name,
                            detail=f"status={state.get('status')}",
                            error=state.get("error"),
                        ),
                    )
                    prev_status = state.get("status")
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Memory persistence soft-failed: %s", exc)

                if on_step is not None:
                    on_step(dict(state))
        except RuntimeError as exc:
            if "cannot schedule new futures after shutdown" in str(exc):
                logger.warning("Caught thread executor shutdown during graph stream: %s", exc)
            else:
                raise

        if state.get("status") == JobStatus.FAILED.value:
            raise WorkflowError(state.get("error") or "Workflow failed")

        return state
    except WorkflowError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Video workflow failed")
        raise WorkflowError(f"Workflow failed: {exc}") from exc
    finally:
        if owned_conn is not None:
            try:
                owned_conn.close()
            except Exception:  # noqa: BLE001
                pass


def run_workflow(user_input: str) -> dict[str, Any]:
    """Compat wrapper: treat free text as a script-source job."""
    request = VideoJobRequest(
        source_type=SourceType.SCRIPT,
        script_text=user_input or "placeholder",
        config=VideoJobConfig(),
    )
    return run_video_workflow(request)
