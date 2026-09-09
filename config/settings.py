"""Environment-backed application settings."""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    whisper_model: str = Field(default="tiny", alias="WHISPER_MODEL")
    use_nested_graph: bool = Field(default=False, alias="USE_NESTED_GRAPH")
    path_only_state: bool = Field(default=True, alias="PATH_ONLY_STATE")
    ffmpeg_pool_workers: int = Field(default=2, alias="FFMPEG_POOL_WORKERS")
    thumbnail_max_variants: int = Field(default=3, alias="THUMBNAIL_MAX_VARIANTS")
    object_detection: bool = Field(default=True, alias="OBJECT_DETECTION")
    trend_cache_ttl_hours: float = Field(default=24.0, alias="TREND_CACHE_TTL_HOURS")
    ffmpeg_path: str = Field(default="", alias="FFMPEG_PATH")
    output_dir: str = Field(default="outputs", alias="OUTPUT_DIR")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    app_env: str = Field(default="development", alias="APP_ENV")
    log_to_file: bool = Field(default=False, alias="LOG_TO_FILE")
    sentry_dsn: str = Field(default="", alias="SENTRY_DSN")
    sentry_traces_sample_rate: float = Field(
        default=0.0, alias="SENTRY_TRACES_SAMPLE_RATE"
    )
    max_upload_mb: int = Field(default=500, alias="MAX_UPLOAD_MB")
    youtube_api_key: str = Field(default="", alias="YOUTUBE_API_KEY")
    youtube_download_enabled: bool = Field(
        default=True, alias="YOUTUBE_DOWNLOAD_ENABLED"
    )
    youtube_download_format: str = Field(
        default="bv*+ba/b",
        alias="YOUTUBE_DOWNLOAD_FORMAT",
    )
    youtube_cookies_file: str = Field(default="", alias="YOUTUBE_COOKIES_FILE")
    gemini_model: str = Field(default="gemini-3.6-flash", alias="GEMINI_MODEL")
    gemini_fallback_models: str = Field(default="", alias="GEMINI_FALLBACK_MODELS")
    gemini_max_retries: int = Field(default=2, alias="GEMINI_MAX_RETRIES")
    gemini_retry_base_seconds: float = Field(default=2.0, alias="GEMINI_RETRY_BASE_SECONDS")
    gemini_retry_max_seconds: float = Field(default=30.0, alias="GEMINI_RETRY_MAX_SECONDS")
    tts_provider: str = Field(default="", alias="TTS_PROVIDER")
    analysis_sample_fps: float = Field(default=1.0, alias="ANALYSIS_SAMPLE_FPS")
    analysis_scene_threshold: float = Field(default=0.35, alias="ANALYSIS_SCENE_THRESHOLD")
    analysis_max_frames: int = Field(default=900, alias="ANALYSIS_MAX_FRAMES")
    scene_min_duration: float = Field(default=1.5, alias="SCENE_MIN_DURATION")
    scene_min_gap: float = Field(default=0.4, alias="SCENE_MIN_GAP")
    scene_max_scenes: int = Field(default=120, alias="SCENE_MAX_SCENES")
    scene_speaker_gap: float = Field(default=1.25, alias="SCENE_SPEAKER_GAP")
    audio_pause_gap: float = Field(default=0.6, alias="AUDIO_PAUSE_GAP")
    audio_volume_spike_db: float = Field(default=6.0, alias="AUDIO_VOLUME_SPIKE_DB")
    audio_max_events: int = Field(default=200, alias="AUDIO_MAX_EVENTS")
    speaker_turn_gap: float = Field(default=0.8, alias="SPEAKER_TURN_GAP")
    moment_min_score: float = Field(default=0.35, alias="MOMENT_MIN_SCORE")
    moment_max_per_category: int = Field(default=40, alias="MOMENT_MAX_PER_CATEGORY")
    moment_min_duration: float = Field(default=1.0, alias="MOMENT_MIN_DURATION")
    moment_merge_gap: float = Field(default=0.75, alias="MOMENT_MERGE_GAP")
    funny_min_humor_score: float = Field(default=0.4, alias="FUNNY_MIN_HUMOR_SCORE")
    funny_max_moments: int = Field(default=50, alias="FUNNY_MAX_MOMENTS")
    funny_setup_window: float = Field(default=4.0, alias="FUNNY_SETUP_WINDOW")
    funny_laughter_weight: float = Field(default=0.25, alias="FUNNY_LAUGHTER_WEIGHT")
    viral_min_final_score: float = Field(default=0.4, alias="VIRAL_MIN_FINAL_SCORE")
    viral_max_moments: int = Field(default=40, alias="VIRAL_MAX_MOMENTS")
    viral_window_pad: float = Field(default=1.5, alias="VIRAL_WINDOW_PAD")
    clip_target_duration: int = Field(default=30, alias="CLIP_TARGET_DURATION")
    clip_duration_tolerance: float = Field(default=0.35, alias="CLIP_DURATION_TOLERANCE")
    clip_max_clips: int = Field(default=20, alias="CLIP_MAX_CLIPS")
    shorts_max_per_duration: int = Field(default=3, alias="SHORTS_MAX_PER_DURATION")
    clip_max_overlap: float = Field(default=0.35, alias="CLIP_MAX_OVERLAP")
    clip_min_score: float = Field(default=0.35, alias="CLIP_MIN_SCORE")
    podcast_max_clips: int = Field(default=25, alias="PODCAST_MAX_CLIPS")
    podcast_min_score: float = Field(default=0.35, alias="PODCAST_MIN_SCORE")
    podcast_target_duration: float = Field(default=45.0, alias="PODCAST_TARGET_DURATION")
    research_max_claims: int = Field(default=40, alias="RESEARCH_MAX_CLAIMS")
    research_max_sources: int = Field(default=60, alias="RESEARCH_MAX_SOURCES")
    research_min_confidence: float = Field(default=0.35, alias="RESEARCH_MIN_CONFIDENCE")
    supervisor_max_steps: int = Field(default=16, alias="SUPERVISOR_MAX_STEPS")
    supervisor_max_retries: int = Field(default=1, alias="SUPERVISOR_MAX_RETRIES")
    calendar_horizon_days: int = Field(default=30, alias="CALENDAR_HORIZON_DAYS")
    calendar_posts_per_week: int = Field(default=7, alias="CALENDAR_POSTS_PER_WEEK")
    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_publishable_key: str = Field(default="", alias="SUPABASE_PUBLISHABLE_KEY")
    supabase_service_role_key: str = Field(default="", alias="SUPABASE_SERVICE_ROLE_KEY")
    supabase_storage_bucket: str = Field(
        default="ai-video-agent", alias="SUPABASE_STORAGE_BUCKET"
    )

    @property
    def has_sentry_dsn(self) -> bool:
        """Return True when a Sentry DSN is configured."""
        return bool(self.sentry_dsn.strip())

    @property
    def has_gemini_api_key(self) -> bool:
        """Return True when a non-empty Gemini API key is configured."""
        return bool(self.gemini_api_key.strip())

    @property
    def has_supabase_storage(self) -> bool:
        """Return True when Supabase Storage service-role credentials are set.

        ``SUPABASE_PUBLISHABLE_KEY`` is optional (docs / future client use only)
        and is **not** required for server-side Storage.
        """
        return bool(
            self.supabase_url.strip()
            and self.supabase_service_role_key.strip()
            and self.supabase_storage_bucket.strip()
        )

    @property
    def has_supabase_publishable_key(self) -> bool:
        """Publishable (anon) key present — optional; unused by Storage client."""
        return bool(self.supabase_publishable_key.strip())

    def storage_config_status(self) -> str:
        """Return ``missing`` | ``configured`` | ``unreachable`` for Storage.

        ``configured`` means credentials are set; live reachability is confirmed
        via ``storage.factory.storage_config_status`` (health check).
        """
        if not self.has_supabase_storage:
            return "missing"
        return "configured"

    @property
    def is_streamlit_cloud(self) -> bool:
        """Best-effort detection of Streamlit Community Cloud."""
        return bool(
            os.getenv("STREAMLIT_SHARING_MODE")
            or os.getenv("IS_STREAMLIT_CLOUD")
            or (os.getenv("HOSTNAME") or "").endswith(".streamlit.app")
        )

    @property
    def has_youtube_api_key(self) -> bool:
        """Return True when a YouTube Data API key is configured."""
        return bool(self.youtube_api_key.strip())

    @property
    def has_tts_provider(self) -> bool:
        """Return True when a non-passthrough TTS provider name is configured."""
        raw = (self.tts_provider or "").strip().lower()
        return bool(raw) and raw not in {"passthrough", "none", "null"}

    def require_gemini_api_key(self) -> str:
        """Return the Gemini API key or raise if missing.

        Used by later prompts that call Gemini; foundation does not invoke this yet.
        """
        from core.errors import ConfigurationError

        key = self.gemini_api_key.strip()
        if not key:
            raise ConfigurationError(
                "GEMINI_API_KEY is not set. Copy .env.example to .env and add your key."
            )
        return key


def _secrets_overlay() -> dict[str, str]:
    """Load selected keys from Streamlit secrets when present (server-side only)."""
    overlay: dict[str, str] = {}
    try:
        import streamlit as st

        secrets = st.secrets
    except Exception:
        return overlay

    for key in (
        "GEMINI_API_KEY",
        "SUPABASE_URL",
        "SUPABASE_PUBLISHABLE_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_STORAGE_BUCKET",
    ):
        try:
            value = secrets.get(key, "")
        except Exception:
            value = ""
        if value:
            overlay[key] = str(value)
    return overlay


@lru_cache
def get_settings() -> Settings:
    """Return cached settings with Streamlit Cloud secret support."""
    overlay = _secrets_overlay()
    if overlay:
        # Env/.env still win for keys already present in the process environment.
        filtered = {k: v for k, v in overlay.items() if not os.getenv(k)}
        if filtered:
            return Settings(**filtered)
    return Settings()
