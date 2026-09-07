"""Caption cue building, export, and burn-in tools."""

from tools.captions.burnin import burn_captions
from tools.captions.catalog import (
    clear_caption_cache,
    default_caption_style,
    default_safe_area,
    list_caption_styles,
    list_platform_safe_areas,
    resolve_caption_style,
    resolve_safe_area,
)
from tools.captions.cues import (
    build_localized_track,
    build_primary_track,
    build_sentence_cues,
    build_word_cues,
    enrich_cues_with_words,
    has_usable_timestamps,
)
from tools.captions.export import (
    ass_is_useful,
    render_ass,
    render_srt,
    render_vtt,
    style_effects,
    write_ass,
    write_srt,
    write_vtt,
)

__all__ = [
    "ass_is_useful",
    "burn_captions",
    "build_localized_track",
    "build_primary_track",
    "build_sentence_cues",
    "build_word_cues",
    "clear_caption_cache",
    "default_caption_style",
    "default_safe_area",
    "enrich_cues_with_words",
    "has_usable_timestamps",
    "list_caption_styles",
    "list_platform_safe_areas",
    "render_ass",
    "render_srt",
    "render_vtt",
    "resolve_caption_style",
    "resolve_safe_area",
    "style_effects",
    "write_ass",
    "write_srt",
    "write_vtt",
]
