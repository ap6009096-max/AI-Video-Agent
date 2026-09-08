"""Build validated jobs from UI input and run the LangGraph workflow."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import streamlit as st

from pydantic import ValidationError

from core.errors import (
    GeminiAuthenticationError,
    GeminiModelUnavailableError,
    GeminiQuotaExhaustedError,
    GeminiTemporaryRateLimitError,
    StorageError,
    VideoAgentError,
    WorkflowError,
    YouTubeAgentError,
)
from core.logging import get_logger
from graph.workflow import run_video_workflow
from schemas.base import JobStatus
from schemas.job import (
    FeatureFlags,
    SourceType,
    VideoJobConfig,
    VideoJobRequest,
    initial_progress_steps,
)
from tools.ffmpeg.bin import resolve_ffmpeg_binary
from tools.media.resolve import save_uploaded_media, validate_media_path
from ui.progress_panel import init_progress_session, update_progress_from_state

logger = get_logger(__name__)


def _friendly_workflow_error(error: BaseException) -> str:
    """Return actionable UI text while retaining technical details in logs."""
    message = str(error)
    if "daily_quota_exhausted" in message or isinstance(error, GeminiQuotaExhaustedError):
        return (
            "Gemini quota exhausted. Story generation could not be completed because "
            "the configured model has exhausted its daily request quota. Completed "
            "pipeline stages were preserved. Resume later, configure another supported "
            "Gemini model, or use a higher quota tier."
        )
    if "temporary_rate_limit" in message or isinstance(error, GeminiTemporaryRateLimitError):
        return "Gemini is temporarily rate limited. The story stage can be resumed later."
    if "authentication" in message or isinstance(error, GeminiAuthenticationError):
        return "Gemini authentication failed. Check GEMINI_API_KEY and its permissions."
    if "model_or_request_invalid" in message or isinstance(error, GeminiModelUnavailableError):
        return "The configured Gemini model or request is invalid. Check GEMINI_MODEL and fallback models."
    return message


def build_job_request(
    source: dict[str, Any],
    config: dict[str, Any],
    features: dict[str, Any],
) -> VideoJobRequest:
    """Validate UI payloads into a VideoJobRequest (may write upload to disk)."""
    from core.mode_mapper import map_mode_to_config
    from tools.voice.reference_analyzer import analyze_reference_voice

    job_id = str(uuid4())
    raw_source_type = source.get("source_type")
    if raw_source_type:
        try:
            source_type = SourceType(raw_source_type)
        except ValueError as exc:
            raise ValueError(f"Unsupported source type: {raw_source_type!r}") from exc
    elif (source.get("youtube_url") or "").strip():
        source_type = SourceType.YOUTUBE
    elif source.get("uploaded_file") is not None:
        source_type = SourceType.UPLOAD
    elif (source.get("script_text") or "").strip():
        source_type = SourceType.SCRIPT
    else:
        raise ValueError(
            "Unable to determine source type. Please provide a YouTube URL "
            "or upload a supported media file."
        )
    upload_path = ""

    # Auto-map config and feature flags if an output_mode was selected in simple UI
    output_mode = source.get("output_mode")
    if output_mode:
        platform = source.get("platform", "")
        style = source.get("visual_style", "")
        mapped_features, mapped_config = map_mode_to_config(output_mode, platform=platform, style=style)
        # Merge explicitly provided features/config if any
        if features:
            for k, v in features.items():
                if hasattr(mapped_features, k):
                    setattr(mapped_features, k, v)
        if config:
            for k, v in config.items():
                if hasattr(mapped_config, k):
                    setattr(mapped_config, k, v)
        features_obj = mapped_features
        config_obj = mapped_config
    else:
        config_obj = VideoJobConfig(**config) if config else VideoJobConfig()
        features_obj = FeatureFlags(**features) if features else FeatureFlags()

    if source_type == SourceType.UPLOAD:
        uploaded = source.get("uploaded_file")
        if uploaded is None:
            raise ValueError("Please upload a video or provide a YouTube URL.")
        upload_path = save_uploaded_media(uploaded, job_id=job_id)
        upload_path = validate_media_path(upload_path)
        st.session_state["resolved_media_path"] = upload_path
        logger.info("[MEDIA] resolved_media_path=%s", upload_path)
    elif source_type == SourceType.YOUTUBE:
        url = (source.get("youtube_url") or "").strip()
        if not url:
            raise ValueError("Please upload a video or provide a YouTube URL.")
        st.session_state.pop("resolved_media_path", None)

    # Handle voice reference upload if present
    uploaded_voice = source.get("uploaded_voice")
    if uploaded_voice is not None:
        try:
            profile = analyze_reference_voice(uploaded_voice)
            if profile and profile.gender != "neutral":
                config_obj.voice = f"{profile.gender.capitalize()} (Ref Voice)"
            logger.info("Analyzed voice reference: %s", profile.to_dict())
        except Exception as exc:  # noqa: BLE001
            logger.info("Voice analysis skipped: %s", exc)

    return VideoJobRequest(
        job_id=job_id,
        source_type=source_type,
        youtube_url=source.get("youtube_url") or "",
        upload_path=upload_path,
        script_text=source.get("script_text") or "",
        config=config_obj,
        features=features_obj,
    )



def run_job_from_ui(
    source: dict[str, Any],
    config: dict[str, Any],
    features: dict[str, Any],
    *,
    resume: bool = False,
    project_id: str = "",
    from_step: str | None = None,
    retry_failed: bool = False,
) -> dict[str, Any] | None:
    """Validate input, stream the LangGraph workflow, and update session progress."""
    init_progress_session()
    progress_slot = st.empty()

    if resolve_ffmpeg_binary() is None:
        msg = (
            "FFmpeg is required for video/audio processing. "
            "The bundled imageio-ffmpeg executable is unavailable; "
            "install FFmpeg locally or set FFMPEG_PATH."
        )
        st.warning(msg)
        logger.warning("[MEDIA] %s", msg)

    try:
        if resume and project_id:
            from core.workflow_memory import load_memory

            mem = load_memory(project_id)
            if mem is None or not mem.job:
                raise ValueError(f"Cannot resume — missing memory/job for {project_id}")
            request = VideoJobRequest.model_validate(mem.job)
            request.job_id = project_id
        else:
            request = build_job_request(source, config, features)
    except (ValueError, ValidationError, VideoAgentError, StorageError, YouTubeAgentError) as exc:
        message = str(exc)
        if isinstance(exc, ValidationError):
            message = "; ".join(err["msg"] for err in exc.errors())
        st.session_state.pipeline_status = JobStatus.FAILED.value
        st.session_state.pipeline_error = message
        st.error(message)
        logger.warning("Job validation failed: %s", message)
        return None

    st.session_state.job_request = request.model_dump(mode="json")
    st.session_state.pipeline_steps = initial_progress_steps()
    st.session_state.pipeline_status = JobStatus.RUNNING.value
    st.session_state.pipeline_error = None
    st.session_state.last_result = None
    st.session_state.pipeline_messages = []
    st.session_state.resume_project_id = project_id or request.job_id

    def _on_step(state: dict[str, Any]) -> None:
        project = state.get("project") if isinstance(state.get("project"), dict) else {}
        meta = state.get("source_metadata") if isinstance(state.get("source_metadata"), dict) else {}
        candidate = (
            (project or {}).get("source_path")
            or (meta or {}).get("local_media_path")
            or st.session_state.get("resolved_media_path")
        )
        if candidate:
            try:
                st.session_state["resolved_media_path"] = validate_media_path(candidate)
            except (ValueError, FileNotFoundError, OSError):
                pass
        update_progress_from_state(state)
        with progress_slot.container():
            from ui.progress_panel import render_progress_panel

            render_progress_panel()

    try:
        label = "Resuming…" if resume else "Generating video…"
        with st.spinner(label):
            result = run_video_workflow(
                request,
                on_step=_on_step,
                resume=resume,
                from_step=from_step,
                project_id=project_id or request.job_id,
                retry_failed=retry_failed,
            )
        update_progress_from_state(result)
        progress_slot.empty()
        logger.info("Job %s finished with status=%s", request.job_id, result.get("status"))
        return result
    except WorkflowError as exc:
        progress_slot.empty()
        st.session_state.pipeline_status = JobStatus.FAILED.value
        friendly = _friendly_workflow_error(exc)
        st.session_state.pipeline_error = friendly
        st.error(friendly)
        logger.error(
            "Workflow error project_id=%s stage=story_generation detail=%s",
            request.job_id,
            exc,
        )
        return None
    except Exception as exc:  # noqa: BLE001
        progress_slot.empty()
        st.session_state.pipeline_status = JobStatus.FAILED.value
        st.session_state.pipeline_error = f"Unexpected error: {exc}"
        st.error(f"Unexpected error: {exc}")
        logger.exception("Unexpected job runner error")
        return None
