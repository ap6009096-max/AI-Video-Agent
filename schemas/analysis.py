"""Video understanding / analysis schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TimeRange(BaseModel):
    start: float
    end: float


class VideoProperties(BaseModel):
    duration_seconds: float = 0.0
    fps: float = 0.0
    width: int = 0
    height: int = 0
    frame_count: int = 0
    video_codec: str = ""
    audio_codec: str = ""


class SampledFrameInfo(BaseModel):
    frame_index: int
    time_seconds: float
    motion_score: float = 0.0
    dominant_colors: list[tuple[int, int, int]] = Field(default_factory=list)


class SceneSegment(BaseModel):
    id: int
    start: float
    end: float
    score: float = 0.0


class VisualChange(BaseModel):
    time_seconds: float
    score: float
    kind: Literal["cut", "motion"] = "cut"


class AudioCharacteristics(BaseModel):
    has_audio: bool = False
    sample_rate: int | None = None
    channels: int | None = None
    mean_volume_db: float | None = None
    silence_ranges: list[TimeRange] = Field(default_factory=list)
    speech_ratio: float | None = None


class SpeakerPresence(BaseModel):
    """Speaker-independent speech activity (from transcript timings)."""

    speech_ranges: list[TimeRange] = Field(default_factory=list)
    estimated_speech_coverage: float = 0.0


class ObjectCue(BaseModel):
    """Lightweight practical visual cue (not ML object detection)."""

    label: Literal["motion_hotspot", "color_cluster"]
    time_seconds: float
    detail: str = ""


class VideoAnalysisReport(BaseModel):
    project_id: str
    media_path: str = ""
    sample_fps: float = 1.0
    frames_analyzed: int = 0
    properties: VideoProperties = Field(default_factory=VideoProperties)
    sampled_frames: list[SampledFrameInfo] = Field(default_factory=list)
    scenes: list[SceneSegment] = Field(default_factory=list)
    visual_changes: list[VisualChange] = Field(default_factory=list)
    audio: AudioCharacteristics = Field(default_factory=AudioCharacteristics)
    speaker_presence: SpeakerPresence = Field(default_factory=SpeakerPresence)
    object_cues: list[ObjectCue] = Field(default_factory=list)
    provider: str = "opencv-ffmpeg"
    created_at: datetime = Field(default_factory=_utc_now)
    notes: str = ""


class VideoUnderstandingResult(BaseModel):
    analysis: VideoAnalysisReport
    analysis_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "analysis": self.analysis.model_dump(mode="json"),
            "messages": list(self.messages),
        }
