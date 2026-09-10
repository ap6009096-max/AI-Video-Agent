"""Tests for environment-backed settings."""

from __future__ import annotations

import sys
from types import SimpleNamespace

from config.settings import Settings, get_settings


def test_settings_defaults(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("WHISPER_MODEL", raising=False)
    monkeypatch.delenv("FFMPEG_PATH", raising=False)
    monkeypatch.delenv("OUTPUT_DIR", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("MAX_UPLOAD_MB", raising=False)
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    monkeypatch.delenv("YOUTUBE_DOWNLOAD_ENABLED", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("ANALYSIS_SAMPLE_FPS", raising=False)
    monkeypatch.delenv("ANALYSIS_SCENE_THRESHOLD", raising=False)
    monkeypatch.delenv("ANALYSIS_MAX_FRAMES", raising=False)
    monkeypatch.delenv("SCENE_MIN_DURATION", raising=False)
    monkeypatch.delenv("SCENE_MIN_GAP", raising=False)
    monkeypatch.delenv("SCENE_MAX_SCENES", raising=False)
    monkeypatch.delenv("SCENE_SPEAKER_GAP", raising=False)
    monkeypatch.delenv("AUDIO_PAUSE_GAP", raising=False)
    monkeypatch.delenv("AUDIO_VOLUME_SPIKE_DB", raising=False)
    monkeypatch.delenv("AUDIO_MAX_EVENTS", raising=False)
    monkeypatch.delenv("SPEAKER_TURN_GAP", raising=False)
    monkeypatch.delenv("MOMENT_MIN_SCORE", raising=False)
    monkeypatch.delenv("MOMENT_MAX_PER_CATEGORY", raising=False)
    monkeypatch.delenv("MOMENT_MIN_DURATION", raising=False)
    monkeypatch.delenv("MOMENT_MERGE_GAP", raising=False)
    monkeypatch.delenv("FUNNY_MIN_HUMOR_SCORE", raising=False)
    monkeypatch.delenv("FUNNY_MAX_MOMENTS", raising=False)
    monkeypatch.delenv("FUNNY_SETUP_WINDOW", raising=False)
    monkeypatch.delenv("FUNNY_LAUGHTER_WEIGHT", raising=False)
    monkeypatch.delenv("VIRAL_MIN_FINAL_SCORE", raising=False)
    monkeypatch.delenv("VIRAL_MAX_MOMENTS", raising=False)
    monkeypatch.delenv("VIRAL_WINDOW_PAD", raising=False)
    monkeypatch.delenv("CLIP_TARGET_DURATION", raising=False)
    monkeypatch.delenv("CLIP_DURATION_TOLERANCE", raising=False)
    monkeypatch.delenv("CLIP_MAX_CLIPS", raising=False)
    monkeypatch.delenv("CLIP_MAX_OVERLAP", raising=False)
    monkeypatch.delenv("CLIP_MIN_SCORE", raising=False)
    monkeypatch.delenv("PODCAST_MAX_CLIPS", raising=False)
    monkeypatch.delenv("PODCAST_MIN_SCORE", raising=False)
    monkeypatch.delenv("PODCAST_TARGET_DURATION", raising=False)
    monkeypatch.delenv("RESEARCH_MAX_CLAIMS", raising=False)
    monkeypatch.delenv("RESEARCH_MAX_SOURCES", raising=False)
    monkeypatch.delenv("RESEARCH_MIN_CONFIDENCE", raising=False)
    monkeypatch.delenv("SUPERVISOR_MAX_STEPS", raising=False)
    monkeypatch.delenv("SUPERVISOR_MAX_RETRIES", raising=False)
    monkeypatch.delenv("CALENDAR_HORIZON_DAYS", raising=False)
    monkeypatch.delenv("CALENDAR_POSTS_PER_WEEK", raising=False)
    get_settings.cache_clear()

    settings = Settings(_env_file=None)

    assert settings.gemini_api_key == ""
    assert settings.whisper_model == "tiny"
    assert settings.ffmpeg_path == ""
    assert settings.output_dir == "outputs"
    assert settings.log_level == "INFO"
    assert settings.app_env == "development"
    assert settings.max_upload_mb == 500
    assert settings.youtube_api_key == ""
    assert settings.has_youtube_api_key is False
    assert settings.youtube_download_enabled is True
    assert settings.gemini_model == "gemini-3.6-flash"
    assert settings.has_gemini_api_key is False
    assert settings.analysis_sample_fps == 1.0
    assert settings.analysis_scene_threshold == 0.35
    assert settings.analysis_max_frames == 900
    assert settings.scene_min_duration == 1.5
    assert settings.scene_min_gap == 0.4
    assert settings.scene_max_scenes == 120
    assert settings.scene_speaker_gap == 1.25
    assert settings.audio_pause_gap == 0.6
    assert settings.audio_volume_spike_db == 6.0
    assert settings.audio_max_events == 200
    assert settings.speaker_turn_gap == 0.8
    assert settings.moment_min_score == 0.35
    assert settings.moment_max_per_category == 40
    assert settings.moment_min_duration == 1.0
    assert settings.moment_merge_gap == 0.75
    assert settings.funny_min_humor_score == 0.4
    assert settings.funny_max_moments == 50
    assert settings.funny_setup_window == 4.0
    assert settings.funny_laughter_weight == 0.25
    assert settings.viral_min_final_score == 0.4
    assert settings.viral_max_moments == 40
    assert settings.viral_window_pad == 1.5
    assert settings.clip_target_duration == 30
    assert settings.clip_duration_tolerance == 0.35
    assert settings.clip_max_clips == 20
    assert settings.clip_max_overlap == 0.35
    assert settings.clip_min_score == 0.35
    assert settings.podcast_max_clips == 25
    assert settings.podcast_min_score == 0.35
    assert settings.podcast_target_duration == 45.0
    assert settings.research_max_claims == 40
    assert settings.research_max_sources == 60
    assert settings.research_min_confidence == 0.35
    assert settings.supervisor_max_steps == 16
    assert settings.supervisor_max_retries == 1
    assert settings.calendar_horizon_days == 30
    assert settings.calendar_posts_per_week == 7


def test_settings_env_override(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")
    monkeypatch.setenv("WHISPER_MODEL", "small")
    monkeypatch.setenv("OUTPUT_DIR", "custom_out")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    get_settings.cache_clear()

    settings = Settings(_env_file=None)

    assert settings.gemini_api_key == "test-key-123"
    assert settings.has_gemini_api_key is True
    assert settings.whisper_model == "small"
    assert settings.output_dir == "custom_out"
    assert settings.log_level == "DEBUG"


def test_get_settings_is_cached(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "cached")
    get_settings.cache_clear()

    a = get_settings()
    b = get_settings()
    assert a is b
    get_settings.cache_clear()


def test_get_settings_uses_environment_key(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "environment-key")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.has_gemini_api_key is True
    get_settings.cache_clear()


def test_get_settings_survives_streamlit_import_failure(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setitem(sys.modules, "streamlit", None)
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.has_gemini_api_key is False
    get_settings.cache_clear()


def test_get_settings_uses_streamlit_secret(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    streamlit = SimpleNamespace(secrets={"GEMINI_API_KEY": "streamlit-key"})
    monkeypatch.setitem(sys.modules, "streamlit", streamlit)
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.has_gemini_api_key is True
    get_settings.cache_clear()


def test_supabase_url_strips_duplicated_key_prefix(monkeypatch) -> None:
    monkeypatch.setenv(
        "SUPABASE_URL",
        "SUPABASE_URL=https://example.supabase.co",
    )
    get_settings.cache_clear()

    settings = Settings(_env_file=None)

    assert settings.supabase_url == "https://example.supabase.co"
    get_settings.cache_clear()


def test_youtube_auth_fallback_settings(monkeypatch) -> None:
    monkeypatch.setenv("YOUTUBE_COOKIES_FROM_BROWSER", "edge")
    monkeypatch.setenv("YOUTUBE_AUTH_FALLBACK", "false")
    get_settings.cache_clear()

    settings = Settings(_env_file=None)

    assert settings.youtube_cookies_from_browser == "edge"
    assert settings.youtube_auth_fallback is False
    get_settings.cache_clear()
