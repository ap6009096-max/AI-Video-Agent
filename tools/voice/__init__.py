"""Voice catalog and TTS provider tools."""

from tools.voice.catalog import (
    build_voice_pack,
    clear_voice_cache,
    list_voices,
    resolve_voice,
)
from tools.voice.locale_map import (
    SUPPORTED_VOICE_LANGUAGES,
    normalize_language,
    resolve_edge_voice,
)
from tools.voice.prosody import build_prosody
from tools.voice.provider import (
    EdgeTTSProvider,
    PassthroughTTSProvider,
    get_tts_provider,
)

__all__ = [
    "SUPPORTED_VOICE_LANGUAGES",
    "EdgeTTSProvider",
    "PassthroughTTSProvider",
    "build_prosody",
    "build_voice_pack",
    "clear_voice_cache",
    "get_tts_provider",
    "list_voices",
    "normalize_language",
    "resolve_edge_voice",
    "resolve_voice",
]
