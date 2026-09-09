"""Mode Mapper — maps output mode labels to FeatureFlags + VideoJobConfig presets.

The 7 output modes each auto-configure a specific pipeline.  No user-facing
feature toggles are required when using the simple UI.
"""

from __future__ import annotations

from typing import Any

from schemas.job import FeatureFlags, VideoJobConfig

# Human-readable output mode labels (displayed in the Streamlit UI)
OUTPUT_MODES: list[str] = [
    "Animated Podcast",
    "Funny Podcast",
    "Simple Podcast",
    "Rewrite + Keep Original Video",
    "Voice Transformation",
    "Scene Transformation",
    "Full AI Transformation",
]

OUTPUT_MODE_SLUGS: dict[str, str] = {
    "Animated Podcast": "animated_podcast",
    "Funny Podcast": "funny_podcast",
    "Simple Podcast": "simple_podcast",
    "Rewrite + Keep Original Video": "rewrite_keep_video",
    "Voice Transformation": "voice_transformation",
    "Scene Transformation": "scene_transformation",
    "Full AI Transformation": "full_ai_transformation",
}


def _animated_podcast() -> tuple[FeatureFlags, VideoJobConfig]:
    flags = FeatureFlags(
        smart_clip_detection=True,
        podcast_clips=True,
        captions=True,
        voice=True,
        smart_reframing=True,
        storyboard=True,
        camera=True,
        platform_optimization=True,
        funny_moments=True,
        emotional_moments=True,
    )
    config = VideoJobConfig(
        video_type="Podcast",
        caption_style="Kinetic",
        caption_burn_in=True,
        reframe_aspect="9:16",
        platform="YouTube Shorts",
        target_clip_duration=60,
    )
    return flags, config


def _funny_podcast() -> tuple[FeatureFlags, VideoJobConfig]:
    flags = FeatureFlags(
        smart_clip_detection=True,
        funny_moments=True,
        viral_moments=True,
        podcast_clips=True,
        captions=True,
        platform_optimization=True,
        smart_reframing=True,
        emotional_moments=True,
    )
    config = VideoJobConfig(
        video_type="Podcast",
        caption_style="Pop",
        caption_burn_in=True,
        reframe_aspect="9:16",
        platform="YouTube Shorts",
        target_clip_duration=45,
    )
    return flags, config


def _simple_podcast() -> tuple[FeatureFlags, VideoJobConfig]:
    flags = FeatureFlags(
        smart_clip_detection=True,
        podcast_clips=True,
        captions=True,
        platform_optimization=True,
        smart_reframing=True,
        important_moments=True,
        viral_moments=True,
    )
    config = VideoJobConfig(
        video_type="Podcast",
        caption_style="Platform Safe",
        caption_burn_in=True,
        reframe_aspect="9:16",
        platform="YouTube Shorts",
        target_clip_duration=60,
    )
    return flags, config


def _rewrite_keep_video() -> tuple[FeatureFlags, VideoJobConfig]:
    flags = FeatureFlags(
        smart_clip_detection=True,
        captions=True,
        voice=True,
        platform_optimization=True,
        podcast_clips=True,
    )
    config = VideoJobConfig(
        video_type="Podcast",
        caption_style="Platform Safe",
        caption_burn_in=True,
        voice="AI Voice",
        target_clip_duration=60,
    )
    return flags, config


def _voice_transformation() -> tuple[FeatureFlags, VideoJobConfig]:
    flags = FeatureFlags(
        captions=True,
        voice=True,
        platform_optimization=True,
        smart_clip_detection=True,
    )
    config = VideoJobConfig(
        caption_style="Platform Safe",
        caption_burn_in=True,
        voice="AI Voice",
    )
    return flags, config


def _scene_transformation() -> tuple[FeatureFlags, VideoJobConfig]:
    flags = FeatureFlags(
        smart_clip_detection=True,
        captions=True,
        smart_reframing=True,
        camera=True,
        platform_optimization=True,
        podcast_clips=True,
        funny_moments=True,
        viral_moments=True,
        scene_transform=True,
        multi_shorts_export=True,
    )
    config = VideoJobConfig(
        caption_style="Platform Safe",
        caption_burn_in=True,
        reframe_aspect="9:16",
        target_clip_duration=30,
        short_durations=[30, 60, 90],
    )
    return flags, config


def _full_ai_transformation() -> tuple[FeatureFlags, VideoJobConfig]:
    flags = FeatureFlags(
        smart_clip_detection=True,
        viral_moments=True,
        funny_moments=True,
        emotional_moments=True,
        important_moments=True,
        podcast_clips=True,
        captions=True,
        voice=True,
        smart_reframing=True,
        storyboard=True,
        camera=True,
        platform_optimization=True,
        thumbnail=True,
        seo=True,
        analytics=True,
        trend=True,
        repurpose=True,
        b_roll=True,
    )
    config = VideoJobConfig(
        video_type="Podcast",
        caption_style="Kinetic",
        caption_burn_in=True,
        reframe_aspect="9:16",
        platform="YouTube Shorts",
        target_clip_duration=60,
        voice="AI Voice",
    )
    return flags, config


_MODE_BUILDERS: dict[str, Any] = {
    "animated_podcast": _animated_podcast,
    "funny_podcast": _funny_podcast,
    "simple_podcast": _simple_podcast,
    "rewrite_keep_video": _rewrite_keep_video,
    "voice_transformation": _voice_transformation,
    "scene_transformation": _scene_transformation,
    "full_ai_transformation": _full_ai_transformation,
}


def map_mode_to_config(
    output_mode: str,
    platform: str = "",
    style: str = "",
) -> tuple[FeatureFlags, VideoJobConfig]:
    """Return (FeatureFlags, VideoJobConfig) preset for the given output mode label or slug.

    Args:
        output_mode: Either a human label ("Simple Podcast") or slug ("simple_podcast").
        platform: Optional platform override (e.g. "TikTok").
        style: Optional visual style override.

    Returns:
        Tuple of (FeatureFlags, VideoJobConfig) configured for the mode.
    """
    # Resolve slug
    slug = OUTPUT_MODE_SLUGS.get(output_mode, output_mode)
    builder = _MODE_BUILDERS.get(slug)
    if builder is None:
        # Default fallback — simple podcast
        builder = _simple_podcast

    flags, config = builder()

    # Apply optional overrides
    if platform and platform.strip():
        config.platform = platform.strip()
    if style and style.strip() not in ("", "Automatic"):
        config.visual_style = style.strip()

    return flags, config


def mode_needs_voice(output_mode: str) -> bool:
    """Return True if this mode generates new voice audio."""
    slug = OUTPUT_MODE_SLUGS.get(output_mode, output_mode)
    return slug in {"animated_podcast", "rewrite_keep_video", "voice_transformation", "full_ai_transformation"}


def mode_needs_script(output_mode: str) -> bool:
    """Return True if a user-supplied script is particularly relevant for this mode."""
    slug = OUTPUT_MODE_SLUGS.get(output_mode, output_mode)
    return slug in {"rewrite_keep_video", "voice_transformation", "full_ai_transformation"}


def mode_is_podcast_focused(output_mode: str) -> bool:
    """Return True if this mode is primarily oriented toward podcast content."""
    slug = OUTPUT_MODE_SLUGS.get(output_mode, output_mode)
    return slug in {"animated_podcast", "funny_podcast", "simple_podcast"}
