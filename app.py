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


def _render_sidebar() -> None:
    st.sidebar.header("Configuration")
    st.sidebar.markdown(f"**Environment:** `{settings.app_env}`")
    st.sidebar.markdown(
        f"**Gemini API key:** {'configured' if settings.has_gemini_api_key else 'missing'}"
    )
    st.sidebar.markdown(
        f"**Sentry:** {'enabled' if settings.has_sentry_dsn else 'off'}"
    )
    tts_raw = (settings.tts_provider or "").strip() or "none"
    if settings.has_tts_provider:
        tts_label = f"{tts_raw} (ready)"
    else:
        tts_label = f"{tts_raw or 'none'} (passthrough)"
    st.sidebar.markdown(f"**TTS provider:** `{tts_label}`")
    st.sidebar.markdown(f"**Whisper model:** `{settings.whisper_model}`")
    from tools.ffmpeg.bin import resolve_ffmpeg_binary

    ffmpeg_bin = resolve_ffmpeg_binary()
    ffmpeg_display = settings.ffmpeg_path.strip() or "(imageio-ffmpeg)"
    if ffmpeg_bin:
        st.sidebar.markdown(f"**FFmpeg:** `ready` (`{ffmpeg_display}`)")
    else:
        st.sidebar.error(
            "FFmpeg is required for video/audio processing. "
            "The bundled imageio-ffmpeg executable is unavailable; "
            "install FFmpeg locally or set FFMPEG_PATH."
        )
    st.sidebar.markdown(
        f"**YouTube download:** "
        f"`{'on' if settings.youtube_download_enabled else 'off (metadata only)'}`"
    )
    st.sidebar.markdown(f"**Output dir:** `{get_output_dir()}`")
    st.sidebar.caption("API keys are never displayed. Set them in `.env`.")
    st.sidebar.divider()
    st.sidebar.markdown("**Creator OS stages**")
    st.sidebar.caption(
        "Research → Planning → Script → Storyboard → Video → "
        "Optimization → Analytics → Publishing Prep"
    )


def main() -> None:
    _render_sidebar()

    st.title("AI VIDEO AGENT")
    st.markdown(
        "**One-Input Automatic Video Transformation Platform** — Provide a video/YouTube URL, "
        "optional script or reference voice, select what you want to create, and the AI handles the rest."
    )

    # Main simple input panel
    source = render_simple_input_form()

    # Optional Advanced Settings expander
    config: dict = {}
    features: dict = {}
    with st.expander("⚙️ Advanced Settings (Optional Override)", expanded=False):
        st.caption("Fine-tune creative parameters and feature toggles manually if needed.")
        config = render_config_form()
        st.divider()
        features = render_feature_toggles()
        st.divider()
        resume_opts = render_resume_controls()

    if "resume_opts" not in locals():
        resume_opts = {}

    st.divider()

    # Main Action Button
    generate = st.button(
        "🎬 CREATE VIDEO", type="primary", use_container_width=True
    )
    if generate:
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

    # Deliverables & playable video player panel
    render_final_output_panel()


main()
