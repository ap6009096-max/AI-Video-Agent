"""Schemas for video generation jobs, feature flags, and pipeline progress."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

from schemas.localization import LocalizationTarget

ALLOWED_UPLOAD_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".webm",
    ".mp3",
    ".wav",
    ".m4a",
    ".flac",
}
ALLOWED_AUDIO_UPLOAD_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac"}

TargetClipDuration = Literal[10, 15, 30, 40, 45, 60, 90]

ALLOWED_SHORT_DURATIONS: tuple[int, ...] = (10, 15, 30, 40, 45, 60, 90)


def _default_short_durations() -> list[int]:
    return [30, 60, 90]

HumorAdaptationMode = Literal["original", "localized", "regional", "none"]

PIPELINE_STEPS: tuple[str, ...] = (
    "Source detected",
    "Video loaded",
    "Transcript extracted",
    "Scenes detected",
    "Audio analyzed",
    "Important moments found",
    "Funny moments found",
    "Viral moments found",
    "Clips selected",
    "Story generated",
    "Localization completed",
    "Captions generated",
    "Video rendered",
    "Quality checked",
    "Export completed",
)


class SourceType(str, Enum):
    YOUTUBE = "youtube"
    UPLOAD = "upload"
    SCRIPT = "script"
    IDEA = "idea"


class ProgressStepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class FeatureFlags(BaseModel):
    """Feature toggles for the video generation pipeline."""

    smart_clip_detection: bool = True
    viral_moments: bool = True
    funny_moments: bool = False
    emotional_moments: bool = False
    educational_moments: bool = False
    surprise_moments: bool = False
    important_moments: bool = True
    reaction_moments: bool = False
    inspirational_moments: bool = False
    cinematic_moments: bool = False
    expert_insights: bool = False
    best_quotes: bool = False
    b_roll: bool = False
    image_generation: bool = False
    storyboard: bool = False
    character: bool = False
    camera: bool = False
    director: bool = False
    motion_graphics: bool = False
    documentary: bool = False
    scene_transform: bool = False
    podcast_clips: bool = False
    research: bool = False
    supervisor_crew: bool = False
    video_generation: bool = False
    captions: bool = True
    voice: bool = False
    music: bool = False
    avatar: bool = False
    thumbnail: bool = False
    seo: bool = False
    trend: bool = False
    repurpose: bool = False
    content_calendar: bool = False
    brand: bool = False
    analytics: bool = False
    cultural_adaptation: bool = False
    regional_humor: bool = False
    smart_reframing: bool = False
    platform_optimization: bool = True
    multi_shorts_export: bool = False


class VideoJobConfig(BaseModel):
    """Creative and localization configuration for a job."""

    video_type: str = "Shorts"
    visual_style: str = "Cinematic"
    environment: str = "Wildlife/Nature Forest"
    country: str = "United States"
    region: str = "Global"
    language: str = "English"
    audience: str = "General"
    voice: str = "Original Voice"
    voice_emotion: str = "neutral"
    voice_speed: float = 1.0
    voice_pitch: float = 1.0
    avatar: str = "No Avatar"
    avatar_expression: str = ""
    avatar_gesture: str = ""
    thumbnail_platform: str = ""
    seo_platform: str = ""
    brand_name: str = ""
    brand_preset: str = ""
    repurpose_source: str = ""
    humor_style: str = "None"
    humor_adaptation: HumorAdaptationMode = "none"
    platform: str = "YouTube Shorts"
    target_clip_duration: TargetClipDuration = 30
    short_durations: list[int] = Field(default_factory=_default_short_durations)
    music: str = "Original Audio"
    caption_style: str = "Platform Safe"
    caption_emoji: bool = False
    caption_burn_in: bool = True
    reframe_aspect: str = ""
    localization_targets: list[LocalizationTarget] = Field(default_factory=list)
    transform_instruction: str = ""
    transform_scene_id: str = ""
    transform_speaker: str = ""

    @field_validator("short_durations", mode="before")
    @classmethod
    def normalize_short_durations(cls, value: Any) -> list[int]:
        if value is None:
            return list(_default_short_durations())
        if isinstance(value, (int, float)):
            value = [int(value)]
        if not isinstance(value, list):
            return list(_default_short_durations())
        out: list[int] = []
        for item in value:
            try:
                d = int(item)
            except (TypeError, ValueError):
                continue
            if d in ALLOWED_SHORT_DURATIONS and d not in out:
                out.append(d)
        return out or list(_default_short_durations())


class ProgressStep(BaseModel):
    """One step in the generation progress panel."""

    id: int
    label: str
    status: ProgressStepStatus = ProgressStepStatus.PENDING


class VideoJobRequest(BaseModel):
    """Full request payload submitted from the Streamlit UI to LangGraph."""

    job_id: str = Field(default_factory=lambda: str(uuid4()))
    source_type: SourceType
    youtube_url: str = ""
    upload_path: str = ""
    script_text: str = ""
    config: VideoJobConfig = Field(default_factory=VideoJobConfig)
    features: FeatureFlags = Field(default_factory=FeatureFlags)
    # Preflight durable storage refs (from persist/stage before Input Agent)
    storage_bucket: str = ""
    storage_path: str = ""
    original_filename: str = ""
    mime_type: str = ""
    file_size: int = 0

    @field_validator("youtube_url")
    @classmethod
    def normalize_youtube_url(cls, value: str) -> str:
        return value.strip()

    @field_validator("script_text")
    @classmethod
    def normalize_script(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_source_payload(self) -> VideoJobRequest:
        if self.source_type == SourceType.YOUTUBE:
            url = self.youtube_url.lower()
            if not self.youtube_url:
                raise ValueError("YouTube URL is required.")
            if "youtube.com" not in url and "youtu.be" not in url:
                raise ValueError("URL must be a valid YouTube link (youtube.com or youtu.be).")
        elif self.source_type == SourceType.UPLOAD:
            if not self.upload_path:
                raise ValueError("Uploaded video path is required.")
            ext = Path(self.upload_path).suffix.lower()
            if ext not in ALLOWED_UPLOAD_EXTENSIONS:
                raise ValueError(
                    f"Unsupported upload format '{ext}'. "
                    f"Allowed: {', '.join(sorted(ALLOWED_UPLOAD_EXTENSIONS))}"
                )
        elif self.source_type == SourceType.SCRIPT:
            if not self.script_text:
                raise ValueError("Script text is required.")
        elif self.source_type == SourceType.IDEA:
            if not self.script_text:
                raise ValueError("Idea brief text is required.")
        return self


def initial_progress_steps() -> list[dict[str, Any]]:
    """Return pipeline steps as serializable dicts, all pending."""
    return [
        ProgressStep(id=i, label=label).model_dump(mode="json")
        for i, label in enumerate(PIPELINE_STEPS)
    ]
