"""Slim checkpoint state to path refs (Phase 2 path-only cutover)."""

from __future__ import annotations

from typing import Any

from schemas.project_refs import dual_write_paths, refs_from_project_dir

# Pack keys that should not be embedded when PATH_ONLY_STATE is on
HEAVY_PACK_KEYS: tuple[str, ...] = (
    "transcript",
    "speech_transcript",
    "analysis",
    "scenes",
    "audio_analysis",
    "speakers",
    "funny_moments",
    "viral_moments",
    "moments",
    "clips",
    "podcast_clips",
    "research_report",
    "stories",
    "scripts",
    "storyboard_pack",
    "character_pack",
    "camera_pack",
    "director_pack",
    "motion_graphics_pack",
    "documentary_pack",
    "video_generation_pack",
    "image_pack",
    "broll_pack",
    "voice_pack",
    "avatar_pack",
    "music_pack",
    "captions_pack",
    "reframe_pack",
    "platform_pack",
    "brand_pack",
    "seo_pack",
    "trend_pack",
    "repurpose_pack",
    "calendar_pack",
    "thumbnail_pack",
    "analytics_pack",
    "render_pack",
    "quality_pack",
    "export_pack",
    "shared_ai_analysis",
    "objects_pack",
    "competitor_pack",
    "localizations",
    "cultural_adaptation",
    "humor_localization",
    "locale_pack",
    "country_profile",
    "region_profile",
    "video_type_pack",
    "visual_style_pack",
    "environment_pack",
    "supervisor_crew",
)


def slim_state_for_checkpoint(state: dict[str, Any]) -> dict[str, Any]:
    """Keep path refs; drop heavy packs from a checkpoint-oriented copy."""
    out = dual_write_paths(dict(state), project_dir=state.get("project_dir"))
    root = out.get("project_dir")
    if root:
        for k, v in refs_from_project_dir(str(root)).items():
            out.setdefault(k, v)
    for key in HEAVY_PACK_KEYS:
        out.pop(key, None)
    return out
