"""Base Pydantic schemas for jobs, assets, and agent state."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class JobStatus(str, Enum):
    """Lifecycle status for a processing job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class BaseJob(BaseModel):
    """Minimal job record persisted later as JSON metadata."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=_utc_now)
    status: JobStatus = JobStatus.PENDING
    message: str = ""


class VideoAsset(BaseModel):
    """Reference to a local video file and optional metadata."""

    path: str
    duration_seconds: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentStateModel(BaseModel):
    """Pydantic mirror of LangGraph workflow state fields."""

    input: str = ""
    status: JobStatus = JobStatus.PENDING
    messages: list[str] = Field(default_factory=list)
    error: str | None = None
