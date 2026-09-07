"""Simple Input Form — single-panel Streamlit UI for AI Video Agent.

Provides the streamlined user experience:
1. Video / YouTube URL (or file upload)
2. Optional Script (upload .txt/.md/.docx/.pdf OR paste text)
3. Optional Voice (upload reference audio)
4. What do you want to create? (7 output mode selection)
5. Platform & Style overrides (default: YouTube Shorts / Automatic)
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from config.settings import get_settings
from tools.scripts.ingest import extract_script_text
from ui.constants import ALLOWED_UPLOAD_TYPES, OUTPUT_MODES, PLATFORMS, VISUAL_STYLES


def render_simple_input_form() -> dict[str, Any]:
    """Render the simple one-input video transformation form."""
    st.markdown("### AI VIDEO AGENT")
    st.caption(
        "Paste a YouTube URL or upload a video, optionally supply a script and/or reference voice, "
        "select what you want to create, and click **CREATE VIDEO**."
    )

    col1, col2 = st.columns([3, 2])

    with col1:
        # 1. Video / Media Input
        st.markdown("#### 1. Video Source")
        input_type = st.radio(
            "Video Input Method",
            options=["YouTube URL", "Upload Video / Audio File"],
            horizontal=True,
            label_visibility="collapsed",
        )

        youtube_url = ""
        uploaded_file = None

        if input_type == "YouTube URL":
            download_enabled = get_settings().youtube_download_enabled
            youtube_url = st.text_input(
                "YouTube URL",
                placeholder="https://www.youtube.com/watch?v=...",
                help="The AI will download, analyze, transcribe, and transform this video.",
            )
            if not download_enabled:
                st.warning("YouTube download is disabled in .env (YOUTUBE_DOWNLOAD_ENABLED=false).")
        else:
            uploaded_file = st.file_uploader(
                "Upload MP4/MOV/MKV/WebM or MP3/WAV/M4A/FLAC",
                type=ALLOWED_UPLOAD_TYPES,
                help="Local video or podcast audio file to transform.",
            )

        st.divider()

        # 2. Optional Script Input
        st.markdown("#### 2. Optional Script")
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
                    st.success(f"Extracted {len(extracted)} characters from `{uploaded_script_file.name}`")
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

        # 3. Optional Voice Input
        st.markdown("#### 3. Optional Voice Reference")
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
        # 4. Output Mode Selection
        st.markdown("#### 4. What do you want to create?")
        output_mode = st.radio(
            "Output Mode",
            options=OUTPUT_MODES,
            index=2,  # Default: Simple Podcast
            label_visibility="collapsed",
        )

        st.divider()

        # 5. Quick Settings
        st.markdown("#### 5. Quick Format & Style")
        platform = st.selectbox(
            "Platform",
            options=PLATFORMS,
            index=PLATFORMS.index("YouTube Shorts") if "YouTube Shorts" in PLATFORMS else 0,
        )

        styles_with_auto = ["Automatic"] + VISUAL_STYLES
        visual_style = st.selectbox(
            "Visual Style",
            options=styles_with_auto,
            index=0,
        )

    # Determine source_type string for job runner
    if youtube_url.strip():
        source_type = "youtube"
    elif uploaded_file is not None:
        source_type = "upload"
    elif script_text.strip():
        source_type = "script"
    else:
        source_type = "youtube"  # default fallback

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
    }
