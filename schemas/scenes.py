"""Scene detection schemas (authoritative scenes.json)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

ChangeKind = Literal["cut", "transition", "composition", "camera", "speaker", "event"]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DetectedScene(BaseModel):
    id: int
    start: float
    end: float
    duration: float
    visual_change_score: float = 0.0
    description: str = ""
    change_kinds: list[ChangeKind] = Field(default_factory=list)


class SceneDetectionReport(BaseModel):
    project_id: str
    media_path: str = ""
    scenes: list[DetectedScene] = Field(default_factory=list)
    provider: str = "opencv-ffmpeg"
    created_at: datetime = Field(default_factory=_utc_now)
    notes: str = ""
    source_signals: dict[str, int] = Field(default_factory=dict)


class SceneDetectionResult(BaseModel):
    scenes: SceneDetectionReport
    scenes_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "scenes": self.scenes.model_dump(mode="json"),
            "messages": list(self.messages),
        }
