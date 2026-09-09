"""Build validated jobs from UI input and run the LangGraph workflow."""

from __future__ import annotations

from pathlib import Path
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


def _resolve_prior_project_id() -> str:
    """Best-effort project id for scene-edit auto-resume."""
    candidates: list[str] = []
    raw = st.session_state.get("resume_project_id")
    if raw:
        candidates.append(str(raw).strip())
    last = st.session_state.get("last_result")
    if isinstance(last, dict):
        for key in ("project_id", "job_id"):
            val = last.get(key)
            if val:
                candidates.append(str(val).strip())
        pdir = str(last.get("project_dir") or "").strip()
        if pdir:
            candidates.append(Path(pdir).name)
    snap = st.session_state.get("workflow_state_snapshot") or {}
    if isinstance(snap, dict):
        job = snap.get("job") if isinstance(snap.get("job"), dict) else {}
        project = snap.get("project") if isinstance(snap.get("project"), dict) else {}
        for val in (
            job.get("job_id"),
            project.get("project_id"),
            snap.get("project_dir"),
        ):
            if val:
                text = str(val).strip()
                candidates.append(
                    Path(text).name if "/" in text or "\\" in text else text
                )
    for c in candidates:
        if c and c not in {".", ".."}:
            return c
    return ""


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
        return (
            "The configured Gemini model or request is invalid. "
            "Check GEMINI_MODEL and fallback models."
        )
    if isinstance(error, YouTubeAgentError) or "youtube" in message.lower():
        from ingestion.errors import USER_FACING_YOUTUBE_FAILURE

        try:
            st.session_state["youtube_fallback"] = True
            st.session_state["youtube_ingest_error_detail"] = message[:300]
        except Exception:  # noqa: BLE001
            pass
        return USER_FACING_YOUTUBE_FAILURE
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
    raw_source_type = str(source.get("source_type") or "").strip()
    if raw_source_type:
        try:
            source_type = SourceType(raw_source_type)
        except ValueError as exc:
            raise ValueError(f"Unsupported source type: {raw_source_type!r}") from exc
    elif (source.get("youtube_url") or "").strip():
        source_type = SourceType.YOUTUBE
    elif source.get("uploaded_file") is not None or str(
        source.get("upload_path_override") or ""
    ).strip():
        source_type = SourceType.UPLOAD
    elif (source.get("script_text") or "").strip():
        source_type = SourceType.SCRIPT
    else:
        raise ValueError(
            "Please upload a video or provide a YouTube URL."
        )
    upload_path = ""

    output_mode = source.get("output_mode")
    if output_mode:
        platform = source.get("platform", "")
        style = source.get("visual_style", "")
        mapped_features, mapped_config = map_mode_to_config(
            output_mode, platform=platform, style=style
        )
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

    # Short durations from simple form (or advanced config override)
    raw_durs = source.get("short_durations")
    if raw_durs is None and isinstance(config, dict):
        raw_durs = config.get("short_durations")
    if isinstance(raw_durs, list):
        try:
            config_obj.short_durations = [int(d) for d in raw_durs]
        except (TypeError, ValueError):
            pass
    if config_obj.short_durations:
        features_obj.multi_shorts_export = True
        if not features_obj.smart_clip_detection:
            features_obj.smart_clip_detection = True
    else:
        features_obj.multi_shorts_export = False

    if source_type == SourceType.UPLOAD:
        override = str(source.get("upload_path_override") or "").strip()
        uploaded = source.get("uploaded_file")
        if override:
            upload_path = validate_media_path(override)
            st.session_state["resolved_media_path"] = upload_path
            logger.info("[MEDIA] resolved_media_path=%s (preflight/override)", upload_path)
            # Persist to durable storage when possible
            try:
                from storage.sync import persist_source_media

                ref = persist_source_media(
                    project_id=job_id,
                    local_path=upload_path,
                    source_type="youtube" if source.get("youtube_url") else "upload",
                    source_url=str(source.get("youtube_url") or ""),
                )
                st.session_state["media_ref"] = ref.to_dict()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Preflight storage persist skipped: %s", type(exc).__name__)
        elif uploaded is None:
            raise ValueError("Please upload a video or provide a YouTube URL.")
        else:
            try:
                from ingestion.upload import stage_upload_to_storage

                ref = stage_upload_to_storage(uploaded, project_id=job_id)
                upload_path = validate_media_path(ref.local_path)
                st.session_state["resolved_media_path"] = upload_path
                st.session_state["media_ref"] = ref.to_dict()
                logger.info("[MEDIA] resolved_media_path=%s", upload_path)
            except Exception:
                # Fallback to legacy local-only save
                upload_path = save_uploaded_media(uploaded, job_id=job_id)
                upload_path = validate_media_path(upload_path)
                st.session_state["resolved_media_path"] = upload_path
                logger.info("[MEDIA] resolved_media_path=%s", upload_path)
    elif source_type == SourceType.YOUTUBE:
        url = (source.get("youtube_url") or "").strip()
        if not url:
            raise ValueError("Please upload a video or provide a YouTube URL.")
        st.session_state.pop("resolved_media_path", None)

    uploaded_voice = source.get("uploaded_voice")
    if uploaded_voice is not None:
        try:
            profile = analyze_reference_voice(uploaded_voice)
            if profile and profile.gender != "neutral":
                config_obj.voice = f"{profile.gender.capitalize()} (Ref Voice)"
            logger.info("Analyzed voice reference: %s", profile.to_dict())
        except Exception as exc:  # noqa: BLE001
            logger.info("Voice analysis skipped: %s", exc)

    scene_edit = source.get("scene_edit_request")
    if isinstance(scene_edit, dict):
        instr = str(scene_edit.get("instruction") or "").strip()
        scene_id = str(scene_edit.get("scene_id") or "").strip()
        speaker = str(scene_edit.get("speaker") or "").strip()
        if instr:
            config_obj.transform_instruction = instr
            config_obj.transform_scene_id = scene_id
            config_obj.transform_speaker = speaker
            features_obj.scene_transform = True
            features_obj.multi_shorts_export = True
            if not features_obj.smart_clip_detection:
                features_obj.smart_clip_detection = True

    storage_bucket = ""
    storage_path = ""
    original_filename = ""
    mime_type = ""
    file_size = 0
    try:
        media_ref = st.session_state.get("media_ref")
    except Exception:  # noqa: BLE001
        media_ref = None
    if isinstance(media_ref, dict):
        storage_bucket = str(media_ref.get("storage_bucket") or "")
        storage_path = str(media_ref.get("storage_path") or "")
        original_filename = str(media_ref.get("original_filename") or "")
        mime_type = str(media_ref.get("mime_type") or "")
        try:
            file_size = int(media_ref.get("file_size") or 0)
        except (TypeError, ValueError):
            file_size = 0

    return VideoJobRequest(
        job_id=job_id,
        source_type=source_type,
        youtube_url=source.get("youtube_url") or "",
        upload_path=upload_path,
        script_text=source.get("script_text") or "",
        config=config_obj,
        features=features_obj,
        storage_bucket=storage_bucket,
        storage_path=storage_path,
        original_filename=original_filename,
        mime_type=mime_type,
        file_size=file_size,
    )


def _merge_scene_edit_into_request(request: VideoJobRequest) -> VideoJobRequest:
    """Apply queued scene_edit_request onto the job (fresh or resume)."""
    edit = None
    try:
        edit = st.session_state.get("scene_edit_request")
    except Exception:  # noqa: BLE001
        edit = None
    if not isinstance(edit, dict):
        return request
    instr = str(edit.get("instruction") or "").strip()

    if not instr:
        return request
    request.config.transform_instruction = instr
    request.config.transform_scene_id = str(edit.get("scene_id") or "").strip()
    request.config.transform_speaker = str(edit.get("speaker") or "").strip()
    request.features.scene_transform = True
    request.features.multi_shorts_export = True
    if not request.features.smart_clip_detection:
        request.features.smart_clip_detection = True
    try:
        st.session_state.pop("scene_edit_request", None)
    except Exception:  # noqa: BLE001
        pass
    return request


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

    scene_edit = st.session_state.get("scene_edit_request")
    prior_id = _resolve_prior_project_id()
    if isinstance(scene_edit, dict) and prior_id and not resume:
        resume = True
        project_id = prior_id
        if not from_step:
            from_step = "transform_intent"

    try:
        if resume and project_id:
            from core.workflow_memory import load_memory

            mem = load_memory(project_id)
            if mem is None or not mem.job:
                source = dict(source)
                if isinstance(scene_edit, dict):
                    source["scene_edit_request"] = scene_edit
                resume = False
                from_step = None
                request = build_job_request(source, config, features)
            else:
                request = VideoJobRequest.model_validate(mem.job)
                request.job_id = project_id
        else:
            request = build_job_request(source, config, features)

        request = _merge_scene_edit_into_request(request)
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
    st.session_state.pipeline_messages = []
    st.session_state.resume_project_id = project_id or request.job_id

    def _on_step(state: dict[str, Any]) -> None:
        project = state.get("project") if isinstance(state.get("project"), dict) else {}
        meta = (
            state.get("source_metadata")
            if isinstance(state.get("source_metadata"), dict)
            else {}
        )
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
        if isinstance(result, dict):
            if result.get("result") is not None:
                st.session_state.last_result = result.get("result")
            else:
                from graph.state_view import project_state_view

                st.session_state.last_result = project_state_view(result)
            pid = ""
            lr = st.session_state.last_result
            if isinstance(lr, dict):
                pid = str(lr.get("project_id") or lr.get("job_id") or "")
            if not pid and isinstance(result.get("job"), dict):
                pid = str(result["job"].get("job_id") or "")
            if pid:
                st.session_state.resume_project_id = pid
        progress_slot.empty()
        logger.info(
            "Job %s finished with status=%s", request.job_id, result.get("status")
        )
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
