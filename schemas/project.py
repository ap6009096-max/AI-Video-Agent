"""Project metadata and Input Agent result schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from schemas.base import JobStatus
from schemas.job import SourceType


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DownstreamRoute(str, Enum):
    """Downstream agent route selected by the Input Agent."""

    YOUTUBE_INGEST = "youtube_ingest"
    LOCAL_VIDEO_INGEST = "local_video_ingest"
    SCRIPT_INGEST = "script_ingest"


SOURCE_TO_ROUTE: dict[SourceType, DownstreamRoute] = {
    SourceType.YOUTUBE: DownstreamRoute.YOUTUBE_INGEST,
    SourceType.UPLOAD: DownstreamRoute.LOCAL_VIDEO_INGEST,
    SourceType.SCRIPT: DownstreamRoute.SCRIPT_INGEST,
    SourceType.IDEA: DownstreamRoute.SCRIPT_INGEST,
}


class ProjectMetadata(BaseModel):
    """Persisted project.json payload."""

    project_id: str = Field(default_factory=lambda: str(uuid4()))
    source_type: SourceType
    source_path: str = ""
    youtube_url: str = ""
    raw_text: str = ""
    created_at: datetime = Field(default_factory=_utc_now)
    status: JobStatus = JobStatus.RUNNING
    configuration: dict[str, Any] = Field(default_factory=dict)


class InputAgentResult(BaseModel):
    """Structured Output from the Input Agent for LangGraph state updates."""

    project: ProjectMetadata
    project_dir: str
    next_agent: DownstreamRoute
    messages: list[str] = Field(default_factory=list)
    detected_source_type: SourceType

    def to_state_dict(self) -> dict[str, Any]:
        """Return a partial WorkflowState-compatible update dict."""
        return {
            "project": self.project.model_dump(mode="json"),
            "project_dir": self.project_dir,
            "next_agent": self.next_agent.value,
            "messages": list(self.messages),
        }
