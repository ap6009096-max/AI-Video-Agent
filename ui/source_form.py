"""Source selector and input widgets."""

from __future__ import annotations

from typing import Any

import streamlit as st

from config.settings import get_settings
from ui.constants import (
    ALLOWED_UPLOAD_TYPES,
    SOURCE_LABEL_TO_TYPE_FULL,
    SOURCE_OPTIONS_WITH_IDEA,
)


def render_source_form() -> dict[str, Any]:
    """Render SOURCE controls and return raw UI values (not yet validated)."""
    st.subheader("SOURCE")
    st.caption(
        "Turn an idea, YouTube URL, video/podcast audio upload, or script into a "
        "multi-platform content package."
    )
    source_label = st.radio(
        "Input method",
        options=SOURCE_OPTIONS_WITH_IDEA,
        horizontal=True,
        label_visibility="collapsed",
    )
    source_type = SOURCE_LABEL_TO_TYPE_FULL[source_label]

    youtube_url = ""
    uploaded_file = None
    script_text = ""

    if source_type == "youtube":
        download_enabled = get_settings().youtube_download_enabled
        youtube_url = st.text_input(
            "YouTube URL",
            placeholder="https://www.youtube.com/watch?v=…",
            help=(
                "Downloads authorized media with yt-dlp, then runs Whisper transcription. "
                "Only process content you are authorized to use."
                if download_enabled
                else (
                    "Metadata-only (download disabled). Upload a video, or set "
                    "YOUTUBE_DOWNLOAD_ENABLED=true."
                )
            ),
        )
        if download_enabled:
            st.caption(
                "YouTube URLs are downloaded locally (yt-dlp) into the media folder, "
                "validated, then transcribed. Bundled imageio-ffmpeg handles media "
                "processing. Upload remains available as an alternative."
            )
        else:
            st.caption(
                "YouTube download is disabled. For Whisper/clips, use Upload or enable "
                "YOUTUBE_DOWNLOAD_ENABLED in .env and restart Streamlit."
            )
    elif source_type == "upload":
        uploaded_file = st.file_uploader(
            "Upload video or podcast audio",
            type=ALLOWED_UPLOAD_TYPES,
            help="Video: MP4, MOV, AVI, MKV, WebM. Audio: MP3, WAV, M4A, FLAC.",
        )
    elif source_type == "idea":
        script_text = st.text_area(
            "Idea brief",
            height=160,
            placeholder="Describe the idea, audience, and angle for your content…",
            help="Short creative brief — routed through script ingest like a draft.",
        )
    else:
        script_text = st.text_area(
            "Text / Script",
            height=160,
            placeholder="Paste or write the script for your video…",
        )

    return {
        "source_type": source_type,
        "youtube_url": youtube_url,
        "uploaded_file": uploaded_file,
        "script_text": script_text,
    }
