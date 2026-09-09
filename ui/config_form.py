"""Configuration form for creative and localization settings."""

from __future__ import annotations

from typing import Any

import streamlit as st

from ui.constants import (
    AUDIENCES,
    AVATAR_EXPRESSIONS,
    AVATAR_GESTURES,
    AVATARS,
    CAPTION_STYLES,
    COUNTRIES,
    ENVIRONMENTS,
    HUMOR_ADAPTATION_LABEL_TO_VALUE,
    HUMOR_ADAPTATION_LABELS,
    HUMOR_STYLES,
    LANGUAGES,
    MUSIC_OPTIONS,
    PLATFORMS,
    REFRAME_ASPECTS,
    REGIONS,
    TARGET_CLIP_DURATIONS,
    SHORT_DURATION_OPTIONS,
    THUMBNAIL_PLATFORMS,
    SEO_PLATFORMS,
    REPURPOSE_SOURCES,
    VIDEO_TYPES,
    VISUAL_STYLES,
    VOICE_EMOTIONS,
    VOICES,
)


def render_config_form() -> dict[str, Any]:
    """Render VIDEO TYPE … PLATFORM fields and return selected values."""
    st.subheader("Configuration")
    left, right = st.columns(2)

    with left:
        video_type = st.selectbox(
            "VIDEO TYPE",
            VIDEO_TYPES,
            index=VIDEO_TYPES.index("Shorts"),
        )
        visual_style = st.selectbox(
            "VISUAL STYLE",
            VISUAL_STYLES,
            index=VISUAL_STYLES.index("Cinematic"),
        )
        environment = st.selectbox(
            "ENVIRONMENT",
            ENVIRONMENTS,
            index=ENVIRONMENTS.index("Wildlife/Nature Forest"),
        )
        country = st.selectbox("COUNTRY", COUNTRIES, index=0)
        region = st.selectbox("REGION", REGIONS, index=0)
        target_clip_duration = st.selectbox(
            "TARGET CLIP DURATION (SEC)",
            TARGET_CLIP_DURATIONS,
            index=TARGET_CLIP_DURATIONS.index(30),
        )
        short_durations = st.multiselect(
            "SHORT DURATIONS (MULTI EXPORT)",
            SHORT_DURATION_OPTIONS,
            default=[30, 60, 90],
            help="Used when Multi Shorts Export is enabled — one Short MP4 per selected duration window.",
        )
        voice_emotion = st.selectbox(
            "VOICE EMOTION",
            VOICE_EMOTIONS,
            index=VOICE_EMOTIONS.index("neutral"),
        )
        voice_speed = st.slider("VOICE SPEED", 0.5, 1.5, 1.0, 0.05)
        voice_pitch = st.slider("VOICE PITCH", 0.5, 1.5, 1.0, 0.05)

    with right:
        language = st.selectbox("LANGUAGE", LANGUAGES, index=0)
        audience = st.selectbox("AUDIENCE", AUDIENCES, index=0)
        voice = st.selectbox(
            "VOICE",
            VOICES,
            index=VOICES.index("Original Voice"),
        )
        avatar = st.selectbox(
            "AVATAR",
            AVATARS,
            index=AVATARS.index("No Avatar"),
        )
        avatar_expression = st.selectbox(
            "AVATAR EXPRESSION",
            AVATAR_EXPRESSIONS,
            index=0,
            format_func=lambda x: x or "(preset default)",
        )
        avatar_gesture = st.selectbox(
            "AVATAR GESTURE",
            AVATAR_GESTURES,
            index=0,
            format_func=lambda x: x or "(preset default)",
        )
        music = st.selectbox(
            "MUSIC",
            MUSIC_OPTIONS,
            index=MUSIC_OPTIONS.index("Original Audio"),
        )
        caption_style = st.selectbox(
            "CAPTION STYLE",
            CAPTION_STYLES,
            index=CAPTION_STYLES.index("Platform Safe"),
        )
        caption_emoji = st.checkbox("CAPTION EMOJI", value=False)
        caption_burn_in = st.checkbox("CAPTION BURN-IN", value=True)
        reframe_aspect_label = st.selectbox(
            "REFRAME ASPECT",
            REFRAME_ASPECTS,
            index=REFRAME_ASPECTS.index("Auto"),
        )
        humor_adaptation_label = st.selectbox(
            "HUMOR ADAPTATION", HUMOR_ADAPTATION_LABELS, index=0
        )
        humor_style = st.selectbox("HUMOR STYLE", HUMOR_STYLES, index=0)
        platform = st.selectbox(
            "PLATFORM",
            PLATFORMS,
            index=PLATFORMS.index("YouTube Shorts"),
        )
        thumbnail_platform_label = st.selectbox(
            "THUMBNAIL PLATFORM",
            THUMBNAIL_PLATFORMS,
            index=0,
        )
        seo_platform_label = st.selectbox(
            "SEO PLATFORM",
            SEO_PLATFORMS,
            index=0,
        )
        repurpose_source_label = st.selectbox(
            "REPURPOSE SOURCE",
            REPURPOSE_SOURCES,
            index=0,
        )

    reframe_aspect = (
        "" if reframe_aspect_label == "Auto" else reframe_aspect_label
    )
    thumbnail_platform = (
        ""
        if thumbnail_platform_label == "Same as platform"
        else thumbnail_platform_label
    )
    seo_platform = (
        "" if seo_platform_label == "Same as platform" else seo_platform_label
    )
    repurpose_source = (
        "" if repurpose_source_label == "Auto" else repurpose_source_label
    )

    return {
        "video_type": video_type,
        "visual_style": visual_style,
        "environment": environment,
        "country": country,
        "region": region,
        "language": language,
        "audience": audience,
        "voice": voice,
        "voice_emotion": voice_emotion,
        "voice_speed": float(voice_speed),
        "voice_pitch": float(voice_pitch),
        "avatar": avatar,
        "avatar_expression": avatar_expression,
        "avatar_gesture": avatar_gesture,
        "music": music,
        "caption_style": caption_style,
        "caption_emoji": caption_emoji,
        "caption_burn_in": caption_burn_in,
        "reframe_aspect": reframe_aspect,
        "humor_adaptation": HUMOR_ADAPTATION_LABEL_TO_VALUE[humor_adaptation_label],
        "humor_style": humor_style,
        "platform": platform,
        "thumbnail_platform": thumbnail_platform,
        "seo_platform": seo_platform,
        "repurpose_source": repurpose_source,
        "target_clip_duration": int(target_clip_duration),
        "short_durations": [int(d) for d in short_durations] or [10, 40, 90],
    }
