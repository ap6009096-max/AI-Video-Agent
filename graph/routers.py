"""Feature/source conditional routing helpers for the video graph."""

from __future__ import annotations

from typing import Any

from schemas.base import JobStatus
from schemas.job import FeatureFlags, SourceType, VideoJobConfig


def _job(state: dict[str, Any]) -> dict[str, Any]:
    return state.get("job") or {}


def _features(state: dict[str, Any]) -> FeatureFlags:
    raw = _job(state).get("features") or {}
    if isinstance(raw, FeatureFlags):
        return raw
    try:
        return FeatureFlags.model_validate(raw)
    except Exception:  # noqa: BLE001
        return FeatureFlags()


def _config(state: dict[str, Any]) -> VideoJobConfig:
    raw = _job(state).get("config") or {}
    if isinstance(raw, VideoJobConfig):
        return raw
    try:
        return VideoJobConfig.model_validate(raw)
    except Exception:  # noqa: BLE001
        return VideoJobConfig()


def _failed(state: dict[str, Any]) -> bool:
    return state.get("status") == JobStatus.FAILED.value or bool(state.get("error"))


def is_script_source(state: dict[str, Any]) -> bool:
    source = _job(state).get("source_type") or ""
    if isinstance(source, SourceType):
        return source in (SourceType.SCRIPT, SourceType.IDEA)
    return str(source).lower() in {
        SourceType.SCRIPT.value,
        SourceType.IDEA.value,
    }


def is_video_source(state: dict[str, Any]) -> bool:
    return not is_script_source(state)


def route_failed_or(state: dict[str, Any], failed_key: str, otherwise: str) -> str:
    if _failed(state):
        return failed_key
    return otherwise


def should_run_funny(state: dict[str, Any]) -> bool:
    f = _features(state)
    return bool(f.funny_moments and f.smart_clip_detection)


def should_run_viral(state: dict[str, Any]) -> bool:
    f = _features(state)
    return bool(f.viral_moments and f.smart_clip_detection)


def should_run_broll(state: dict[str, Any]) -> bool:
    return bool(_features(state).b_roll)


def should_run_image_generation(state: dict[str, Any]) -> bool:
    return bool(_features(state).image_generation)


def should_run_storyboard(state: dict[str, Any]) -> bool:
    return bool(_features(state).storyboard)


def should_run_character(state: dict[str, Any]) -> bool:
    return bool(_features(state).character)


def should_run_camera(state: dict[str, Any]) -> bool:
    return bool(_features(state).camera)


def should_run_director(state: dict[str, Any]) -> bool:
    return bool(_features(state).director)


def should_run_motion_graphics(state: dict[str, Any]) -> bool:
    return bool(_features(state).motion_graphics)


def should_run_documentary(state: dict[str, Any]) -> bool:
    return bool(_features(state).documentary)


def should_run_podcast(state: dict[str, Any]) -> bool:
    if bool(_features(state).podcast_clips):
        return True
    from tools.podcast.package import is_podcast_video_type

    return is_podcast_video_type(_config(state).video_type)


def should_run_research(state: dict[str, Any]) -> bool:
    if bool(_features(state).research):
        return True
    job = state.get("job") or {}
    st = job.get("source_type")
    if st is None:
        project = state.get("project") or {}
        st = project.get("source_type") if isinstance(project, dict) else None
    from tools.research.build import is_research_source_type

    return is_research_source_type(st)


def should_run_supervisor_crew(state: dict[str, Any]) -> bool:
    return bool(_features(state).supervisor_crew)


def should_run_video_generation(state: dict[str, Any]) -> bool:
    return bool(_features(state).video_generation)


def should_run_voice(state: dict[str, Any]) -> bool:
    f = _features(state)
    cfg = _config(state)
    voice = (cfg.voice or "").strip().lower()
    if voice in {"original voice", "original", "none"}:
        return False
    return bool(f.voice)


def should_run_music(state: dict[str, Any]) -> bool:
    f = _features(state)
    cfg = _config(state)
    music = (cfg.music or "").strip().lower()
    if music in {"no music", "none", "off"}:
        return False
    return bool(f.music)


def should_run_avatar(state: dict[str, Any]) -> bool:
    f = _features(state)
    cfg = _config(state)
    avatar = (cfg.avatar or "").strip().lower()
    if avatar in {"no avatar", "none", "off", "disabled"}:
        return False
    return bool(f.avatar)


def should_run_thumbnail(state: dict[str, Any]) -> bool:
    return bool(_features(state).thumbnail)


def should_run_seo(state: dict[str, Any]) -> bool:
    return bool(_features(state).seo)


def should_run_brand(state: dict[str, Any]) -> bool:
    return bool(_features(state).brand)


def should_run_trend(state: dict[str, Any]) -> bool:
    return bool(_features(state).trend)


def should_run_repurpose(state: dict[str, Any]) -> bool:
    return bool(_features(state).repurpose)


def should_run_content_calendar(state: dict[str, Any]) -> bool:
    return bool(_features(state).content_calendar)


def should_run_analytics(state: dict[str, Any]) -> bool:
    return bool(_features(state).analytics)


def should_run_cultural(state: dict[str, Any]) -> bool:
    return bool(_features(state).cultural_adaptation)


def should_run_humor(state: dict[str, Any]) -> bool:
    f = _features(state)
    cfg = _config(state)
    if (cfg.humor_adaptation or "none") == "none":
        return False
    return bool(f.regional_humor)


def route_after_speaker(state: dict[str, Any]) -> str:
    """Speaker → moment detection (PROMPT 25 order)."""
    return route_failed_or(state, "speaker_analysis_failed", "continue")


def route_after_moment(state: dict[str, Any]) -> str:
    if _failed(state):
        return "moment_detection_failed"
    if should_run_funny(state):
        return "funny"
    return "skip_funny"


def route_after_funny(state: dict[str, Any]) -> str:
    if _failed(state):
        return "funny_moment_failed"
    if should_run_viral(state):
        return "viral"
    return "skip_viral"


def route_after_viral(state: dict[str, Any]) -> str:
    return route_failed_or(state, "viral_moment_failed", "continue")


def route_after_smart_clip(state: dict[str, Any]) -> str:
    if _failed(state):
        return "smart_clip_failed"
    if should_run_podcast(state):
        return "podcast"
    return "skip_podcast"


def route_after_podcast(state: dict[str, Any]) -> str:
    if _failed(state):
        return "podcast_failed"
    if should_run_research(state):
        return "research"
    return "skip_research"


def route_after_research(state: dict[str, Any]) -> str:
    if _failed(state):
        return "research_failed"
    if should_run_supervisor_crew(state):
        return "supervisor"
    return "story"


def route_after_supervisor(state: dict[str, Any]) -> str:
    from graph.supervisor_crew import route_supervisor_next

    return route_supervisor_next(state)


def route_after_language(state: dict[str, Any]) -> str:
    if _failed(state):
        return "language_failed"
    if should_run_cultural(state):
        return "cultural"
    return "skip_cultural"


def route_after_cultural(state: dict[str, Any]) -> str:
    if _failed(state):
        return "cultural_failed"
    if should_run_humor(state):
        return "humor"
    return "skip_humor"


def route_after_humor(state: dict[str, Any]) -> str:
    return route_failed_or(state, "humor_failed", "continue")


def route_after_environment(state: dict[str, Any]) -> str:
    if _failed(state):
        return "environment_failed"
    if should_run_storyboard(state):
        return "storyboard"
    return "skip_storyboard"


def route_after_storyboard(state: dict[str, Any]) -> str:
    if _failed(state):
        return "storyboard_failed"
    if should_run_character(state):
        return "character"
    return "skip_character"


def route_after_character(state: dict[str, Any]) -> str:
    if _failed(state):
        return "character_failed"
    if should_run_camera(state):
        return "camera"
    return "skip_camera"


def route_after_camera(state: dict[str, Any]) -> str:
    if _failed(state):
        return "camera_failed"
    if should_run_director(state):
        return "director"
    return "skip_director"


def route_after_director(state: dict[str, Any]) -> str:
    if _failed(state):
        return "director_failed"
    if should_run_motion_graphics(state):
        return "motion_graphics"
    return "skip_motion_graphics"


def route_after_motion_graphics(state: dict[str, Any]) -> str:
    if _failed(state):
        return "motion_graphics_failed"
    if should_run_documentary(state):
        return "documentary"
    return "skip_documentary"


def route_after_documentary(state: dict[str, Any]) -> str:
    if _failed(state):
        return "documentary_failed"
    if should_run_video_generation(state):
        return "video_generation"
    return "skip_video_generation"


def route_after_video_generation(state: dict[str, Any]) -> str:
    if _failed(state):
        return "video_generation_failed"
    if should_run_image_generation(state):
        return "image_generation"
    return "skip_image_generation"


def route_after_image_generation(state: dict[str, Any]) -> str:
    if _failed(state):
        return "image_generation_failed"
    if should_run_broll(state):
        return "b_roll"
    return "skip_broll"


def route_after_broll(state: dict[str, Any]) -> str:
    if _failed(state):
        return "b_roll_failed"
    if should_run_voice(state):
        return "voice"
    return "skip_voice"


def route_after_voice(state: dict[str, Any]) -> str:
    if _failed(state):
        return "voice_failed"
    if should_run_avatar(state):
        return "avatar"
    return "skip_avatar"


def route_after_avatar(state: dict[str, Any]) -> str:
    if _failed(state):
        return "avatar_failed"
    if should_run_music(state):
        return "music"
    return "skip_music"


def route_after_music(state: dict[str, Any]) -> str:
    return route_failed_or(state, "music_failed", "continue")


def route_after_platform(state: dict[str, Any]) -> str:
    if _failed(state):
        return "platform_failed"
    if should_run_brand(state):
        return "brand"
    return "skip_brand"


def route_after_brand(state: dict[str, Any]) -> str:
    if _failed(state):
        return "brand_failed"
    if should_run_seo(state):
        return "seo"
    return "skip_seo"


def route_after_seo(state: dict[str, Any]) -> str:
    if _failed(state):
        return "seo_failed"
    if should_run_trend(state):
        return "trend"
    return "skip_trend"


def route_after_trend(state: dict[str, Any]) -> str:
    if _failed(state):
        return "trend_failed"
    if should_run_repurpose(state):
        return "repurpose"
    return "skip_repurpose"


def route_after_repurpose(state: dict[str, Any]) -> str:
    if _failed(state):
        return "repurpose_failed"
    if should_run_content_calendar(state):
        return "content_calendar"
    return "skip_calendar"


def route_after_calendar(state: dict[str, Any]) -> str:
    if _failed(state):
        return "calendar_failed"
    if should_run_thumbnail(state):
        return "thumbnail"
    return "skip_thumbnail"


def route_after_thumbnail(state: dict[str, Any]) -> str:
    if _failed(state):
        return "thumbnail_failed"
    if should_run_analytics(state):
        return "analytics"
    return "skip_analytics"


def route_after_analytics(state: dict[str, Any]) -> str:
    return route_failed_or(state, "analytics_failed", "continue")


def should_run_content_classifier(state: dict[str, Any]) -> bool:
    """Run content classifier for video sources or when output mode is specified."""
    return is_video_source(state) or bool(_job(state).get("output_mode"))


def should_run_animation_plan(state: dict[str, Any]) -> bool:
    """Run animation plan node when animated podcast mode or storyboard is active."""
    mode = str(_job(state).get("output_mode") or "").lower()
    if "animated" in mode:
        return True
    return should_run_storyboard(state)

