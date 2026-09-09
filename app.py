"""AI Video Agent — Streamlit entrypoint.

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

from config.settings import get_settings
from core.logging import configure_logging, get_logger
from core.paths import ensure_output_dir, get_output_dir
from core.sentry import init_sentry
from ingestion.errors import USER_FACING_YOUTUBE_FAILURE, YouTubeDownloadError
from ingestion.youtube import download_youtube
from ui import (
    apply_styles,
    init_progress_session,
    render_config_form,
    render_feature_toggles,
    render_progress_panel,
    run_job_from_ui,
)
from ui.output_panel import render_final_output_panel
from ui.resume_panel import render_resume_controls
from ui.simple_input_form import render_simple_input_form

st.set_page_config(
    page_title="AI Video Agent",
    page_icon="🎬",
    layout="wide",
)

settings = get_settings()
configure_logging(
    settings.log_level,
    app_env=settings.app_env,
    log_to_file=bool(settings.log_to_file),
    output_dir=settings.output_dir,
)
init_sentry(
    settings.sentry_dsn,
    app_env=settings.app_env,
    traces_sample_rate=settings.sentry_traces_sample_rate,
)
logger = get_logger(__name__)
ensure_output_dir()
apply_styles()
init_progress_session()


def _youtube_downloader_status() -> str:
    try:
        import yt_dlp  # noqa: F401

        return "Available"
    except ImportError:
        return "Missing (pip install yt-dlp)"


def _render_sidebar() -> None:
    st.sidebar.header("Health check")
    st.sidebar.markdown(f"**Environment:** `{settings.app_env}`")
    st.sidebar.markdown(
        f"**Gemini API:** `{'Configured' if settings.has_gemini_api_key else 'Missing'}`"
    )
    if not settings.has_gemini_api_key:
        st.sidebar.caption("Set GEMINI_API_KEY in `.env` or Streamlit Secrets.")

    try:
        from storage import storage_config_status, storage_health

        status, status_detail = storage_config_status()
        backend, ok, detail = storage_health()
        if status == "missing":
            label = f"Local mirror · {detail}"
            st.sidebar.markdown(f"**Supabase Storage:** `{label}`")
            if settings.is_streamlit_cloud:
                st.sidebar.warning(
                    "Streamlit Cloud needs SUPABASE_SERVICE_ROLE_KEY "
                    "(and URL/bucket) or media is lost on remount."
                )
            elif bool(settings.supabase_url.strip()) and not bool(
                settings.supabase_service_role_key.strip()
            ):
                st.sidebar.caption(
                    "Optional: paste SUPABASE_SERVICE_ROLE_KEY in `.env` "
                    "to enable durable cloud Storage. Local mirror is fine for MVP."
                )
            else:
                st.sidebar.caption(
                    "Using local object mirror (offline OK). "
                    "Add SUPABASE_* in `.env` when you want durable cloud Storage."
                )
        elif status == "unreachable":
            st.sidebar.markdown(
                f"**Supabase Storage:** `Unreachable → local fallback · {status_detail}`"
            )
            st.sidebar.warning(
                "Supabase credentials are set but Storage is unreachable. "
                "Using local mirror. Create a private bucket named "
                f"`{settings.supabase_storage_bucket or 'ai-video-agent'}` "
                "and verify the service-role key."
            )
        elif ok and backend == "supabase":
            st.sidebar.markdown(f"**Supabase Storage:** `Connected · {detail}`")
        else:
            st.sidebar.markdown(f"**Supabase Storage:** `{backend} · {detail}`")
    except Exception as exc:  # noqa: BLE001
        st.sidebar.markdown(f"**Supabase Storage:** `Error: {type(exc).__name__}`")

    from tools.ffmpeg.bin import resolve_ffmpeg_binary

    ffmpeg_bin = resolve_ffmpeg_binary()
    if ffmpeg_bin:
        st.sidebar.markdown("**FFmpeg:** `Available`")
    else:
        st.sidebar.error("FFmpeg: unavailable — install or set FFMPEG_PATH.")

    st.sidebar.markdown(f"**Whisper:** `{settings.whisper_model}`")
    st.sidebar.markdown(f"**YouTube Downloader:** `{_youtube_downloader_status()}`")
    st.sidebar.markdown(
        f"**YouTube download flag:** "
        f"`{'on' if settings.youtube_download_enabled else 'off'}`"
    )
    st.sidebar.markdown(f"**Output dir:** `{get_output_dir()}`")
    st.sidebar.caption(
        "Secrets are never displayed. "
        "Storage uses SUPABASE_SERVICE_ROLE_KEY server-side only "
        "(publishable key is optional / unused by the Storage client)."
    )
    st.sidebar.divider()
    st.sidebar.markdown("**Creator OS stages**")
    st.sidebar.caption(
        "Research → Planning → Script → Storyboard → Video → "
        "Optimization → Analytics → Publishing Prep"
    )


def _preflight_youtube(url: str) -> str | None:
    """Attempt YouTube download before Creator OS. On failure, arm upload fallback."""
    result = download_youtube(url)
    if result.ok and result.local_path:
        st.session_state.pop("youtube_fallback", None)
        st.session_state.pop("youtube_ingest_error_detail", None)
        st.session_state["preflight_youtube_media"] = result.local_path
        return result.local_path

    err = result.error
    code = err.code if isinstance(err, YouTubeDownloadError) else "unknown"
    detail = err.message if isinstance(err, YouTubeDownloadError) else "download failed"
    logger.warning("YOUTUBE_DOWNLOAD_FAILED code=%s detail=%s", code, detail)
    st.session_state["youtube_fallback"] = True
    st.session_state["youtube_ingest_error_detail"] = f"{code}: {detail}"
    st.error("⚠ YouTube download unavailable")
    st.warning(USER_FACING_YOUTUBE_FAILURE)
    return None


def main() -> None:
    _render_sidebar()

    st.title("AI VIDEO AGENT")
    st.markdown(
        "**One-Input Automatic Video Transformation Platform** — Provide a video/YouTube URL, "
        "optional script or reference voice, select what you want to create, and the AI handles the rest."
    )

    source = render_simple_input_form()

    config: dict = {}
    features: dict = {}
    resume_opts: dict = {}
    with st.expander("⚙️ Advanced Settings (Optional Override)", expanded=False):
        st.caption("Fine-tune creative parameters and feature toggles manually if needed.")
        config = render_config_form()
        st.divider()
        features = render_feature_toggles()
        st.divider()
        resume_opts = render_resume_controls()

    st.divider()

    action_hint = str(source.get("action_hint") or "create")
    col_a, col_b = st.columns(2)
    with col_a:
        process_youtube = st.button(
            "Process YouTube Video",
            type="primary",
            use_container_width=True,
            disabled=action_hint == "upload" and not source.get("youtube_url"),
        )
    with col_b:
        upload_process = st.button(
            "Upload & Process",
            type="primary",
            use_container_width=True,
        )
    # Keep a combined create button for resume / script-only flows
    generate = st.button("🎬 CREATE VIDEO", use_container_width=True)

    run_now = False
    if process_youtube:
        url = str(source.get("youtube_url") or "").strip()
        if not url:
            st.error("Enter a YouTube URL first.")
        else:
            logger.info("SOURCE_REQUESTED type=youtube preflight=true")
            local = _preflight_youtube(url)
            if local:
                source = dict(source)
                source["source_type"] = "upload"
                source["preflight_media_path"] = local
                # Prefer upload path so workflow uses local_video_ingest with real file
                source["existing_media_path"] = local
                run_now = True
            else:
                st.info("Use **Upload Video Instead** below / switch to Upload, then **Upload & Process**.")
                st.rerun()
    elif upload_process or generate:
        source = dict(source)
        url = str(source.get("youtube_url") or "").strip()
        has_upload = source.get("uploaded_file") is not None
        has_script = bool(str(source.get("script_text") or "").strip())
        if upload_process:
            if has_upload:
                source["source_type"] = "upload"
                st.session_state.pop("youtube_fallback", None)
                run_now = True
            elif url and not has_upload:
                # Treat as YouTube process when URL present
                logger.info("SOURCE_REQUESTED type=youtube preflight=true via_upload_btn")
                local = _preflight_youtube(url)
                if local:
                    source["source_type"] = "upload"
                    source["preflight_media_path"] = local
                    source["existing_media_path"] = local
                    run_now = True
                else:
                    st.rerun()
            elif has_script:
                source["source_type"] = "script"
                run_now = True
            else:
                st.error("Please upload a video or provide a YouTube URL.")
        elif generate:
            # CREATE VIDEO: YouTube URL → same preflight as Process YouTube
            if url and not has_upload:
                logger.info("SOURCE_REQUESTED type=youtube preflight=true via_create")
                local = _preflight_youtube(url)
                if local:
                    source["source_type"] = "upload"
                    source["preflight_media_path"] = local
                    source["existing_media_path"] = local
                    run_now = True
                else:
                    st.info("Use **Upload Video Instead** / **Upload & Process**.")
                    st.rerun()
            elif has_upload:
                source["source_type"] = "upload"
                st.session_state.pop("youtube_fallback", None)
                run_now = True
            elif has_script:
                source["source_type"] = "script"
                run_now = True
            else:
                st.error("Please upload a video or provide a YouTube URL.")

    if run_now:
        # If preflight produced media, map into upload_path via job runner helper
        if source.get("preflight_media_path") and not source.get("uploaded_file"):
            source = dict(source)
            source["upload_path_override"] = source["preflight_media_path"]
            source["source_type"] = "upload"
        logger.info(
            "Create video requested source=%s mode=%s resume=%s project=%s",
            source.get("source_type"),
            source.get("output_mode"),
            resume_opts.get("resume"),
            resume_opts.get("project_id"),
        )
        run_job_from_ui(
            source,
            config,
            features,
            resume=bool(resume_opts.get("resume")),
            project_id=str(resume_opts.get("project_id") or ""),
            from_step=resume_opts.get("from_step"),
            retry_failed=bool(resume_opts.get("retry_failed")),
        )

    st.divider()
    render_progress_panel()
    render_final_output_panel()


main()
