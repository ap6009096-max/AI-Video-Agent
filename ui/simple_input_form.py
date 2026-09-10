"""Simple Input Form — YouTube (best-effort) or direct upload."""

from __future__ import annotations

from typing import Any

import streamlit as st

from config.settings import get_settings
from tools.scripts.ingest import extract_script_text
from ui.constants import (
    ALLOWED_UPLOAD_TYPES,
    OUTPUT_MODES,
    PLATFORMS,
    SHORT_DURATION_OPTIONS,
    VISUAL_STYLES,
)


def _render_youtube_fallback() -> Any:
    """Show required YouTube failure copy + upload control on the same page."""
    from ingestion.errors import (
        USER_FACING_YOUTUBE_FAILURE,
        YouTubeDownloadError,
        YouTubeDownloadStatus,
        user_message_for_status,
        user_message_for_youtube_error,
    )

    st.error("⚠ YouTube download unavailable")
    detail = str(st.session_state.get("youtube_ingest_error_detail") or "")
    status_hint = YouTubeDownloadStatus.UNKNOWN
    if detail:
        code = detail.split(":", 1)[0].strip().lower()
        try:
            status_hint = YouTubeDownloadStatus(code)
        except ValueError:
            status_hint = YouTubeDownloadStatus.UNKNOWN
        synthetic = YouTubeDownloadError(
            code,
            detail.split(":", 1)[-1].strip() if ":" in detail else detail,
            status=status_hint,
        )
        st.warning(user_message_for_youtube_error(synthetic))
        st.caption(f"Technical detail (logged): {detail}")
    else:
        st.warning(user_message_for_status(YouTubeDownloadStatus.UNKNOWN))
        st.caption(USER_FACING_YOUTUBE_FAILURE)
    st.info(
        "Direct upload continues the same analysis pipeline — no YouTube download required."
    )
    st.markdown("**Upload Video Instead**")
    return st.file_uploader(
        "Choose File",
        type=ALLOWED_UPLOAD_TYPES,
        key="youtube_fallback_uploader",
        help="Upload MP4/MOV/MKV/WebM or MP3/WAV/M4A after a YouTube failure.",
    )


def render_simple_input_form() -> dict[str, Any]:
    """Render the simple one-input video transformation form."""
    st.markdown("### Source")
    st.caption(
        "YouTube URL ingestion is best-effort on hosted servers. "
        "Direct upload is the reliable path and stores media in durable storage."
    )

    prior_fallback = bool(st.session_state.get("youtube_fallback"))
    options = ["YouTube URL", "Upload Video / Audio"]
    default_index = 1 if prior_fallback else 0
    input_type = st.radio(
        "Source method",
        options=options,
        index=default_index,
        horizontal=True,
        key="source_method_radio",
    )

    youtube_url = ""
    uploaded_file = None
    action_hint = "create"

    col1, col2 = st.columns([3, 2])

    with col1:
        if input_type == "YouTube URL":
            st.markdown("#### YouTube URL")
            download_enabled = get_settings().youtube_download_enabled
            youtube_url = st.text_input(
                "YouTube URL",
                placeholder="https://www.youtube.com/watch?v=...",
                help="Best-effort download via yt-dlp. Restricted videos may fail on Streamlit Cloud.",
                key="youtube_url_input",
            )
            if not download_enabled:
                st.warning(
                    "YouTube download is disabled (YOUTUBE_DOWNLOAD_ENABLED=false)."
                )
            action_hint = "youtube"
            if prior_fallback:
                st.info(
                    "A previous YouTube download failed. You can retry with Process YouTube "
                    "or upload a file below."
                )
                if st.button("Dismiss download error", key="clear_youtube_fallback"):
                    st.session_state.pop("youtube_fallback", None)
                    st.session_state.pop("youtube_ingest_error_detail", None)
                    st.rerun()
                uploaded_file = _render_youtube_fallback()
                if uploaded_file is not None:
                    action_hint = "upload"
        else:
            st.markdown("#### Upload Video / Audio")
            if prior_fallback:
                uploaded_file = _render_youtube_fallback()
            else:
                uploaded_file = st.file_uploader(
                    "Choose File",
                    type=ALLOWED_UPLOAD_TYPES,
                    help="Local video or podcast audio file to transform.",
                )
            action_hint = "upload"

        st.divider()
        st.markdown("#### Optional Script")
        script_tab1, script_tab2 = st.tabs(["Upload Script File", "Paste Text"])

        uploaded_script_file = None
        script_text = ""

        with script_tab1:
            uploaded_script_file = st.file_uploader(
                "Upload .txt, .md, .docx, or .pdf script",
                type=["txt", "md", "docx", "pdf"],
                key="script_file_uploader",
                help="Uploaded script text will be extracted and mapped onto the video.",
            )
            if uploaded_script_file is not None:
                extracted = extract_script_text(uploaded_script_file)
                if extracted:
                    st.success(
                        f"Extracted {len(extracted)} characters from "
                        f"`{uploaded_script_file.name}`"
                    )
                    script_text = extracted

        with script_tab2:
            pasted = st.text_area(
                "Paste Script / Instructions",
                height=120,
                placeholder="Paste new script or scene editing instructions here...",
                key="script_text_area",
            )
            if pasted.strip():
                script_text = pasted.strip()

        st.divider()
        st.markdown("#### Optional Voice Reference")
        uploaded_voice = st.file_uploader(
            "Upload Reference Voice (.wav, .mp3, .m4a, .flac)",
            type=["wav", "mp3", "m4a", "flac"],
            key="voice_file_uploader",
            help=(
                "The AI will analyze pitch/speaking rate/gender of this clip and pick "
                "the closest matching target voice profile."
            ),
        )
        if uploaded_voice is not None:
            st.info(f"Voice reference `{uploaded_voice.name}` attached.")

    with col2:
        st.markdown("#### What do you want to create?")
        output_mode = st.radio(
            "Output Mode",
            options=OUTPUT_MODES,
            index=2,
            label_visibility="collapsed",
        )
        st.divider()
        st.markdown("#### Quick Format & Style")
        platform = st.selectbox(
            "Platform",
            options=PLATFORMS,
            index=PLATFORMS.index("YouTube Shorts")
            if "YouTube Shorts" in PLATFORMS
            else 0,
        )
        styles_with_auto = ["Automatic"] + VISUAL_STYLES
        visual_style = st.selectbox(
            "Visual Style",
            options=styles_with_auto,
            index=0,
        )
        st.divider()
        st.markdown("#### Short durations")
        short_durations = st.multiselect(
            "Generate Shorts (seconds)",
            options=SHORT_DURATION_OPTIONS,
            default=[30, 60, 90],
            help="Real moment-selected vertical Shorts (1080×1920). Empty = no Shorts export.",
        )

    if uploaded_file is not None:
        source_type = "upload"
    elif youtube_url.strip():
        source_type = "youtube"
    elif script_text.strip():
        source_type = "script"
    else:
        # Incomplete: do not pretend YouTube/upload is ready without media
        source_type = ""

    return {
        "source_type": source_type,
        "youtube_url": youtube_url.strip(),
        "uploaded_file": uploaded_file,
        "script_text": script_text,
        "uploaded_script_file": uploaded_script_file,
        "uploaded_voice": uploaded_voice,
        "output_mode": output_mode,
        "platform": platform,
        "visual_style": visual_style,
        "short_durations": [int(d) for d in short_durations],
        "action_hint": action_hint,
        "youtube_fallback": prior_fallback and uploaded_file is not None,
    }
