"""Workflow memory and execution-history schemas (Prompt 26)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

WORKFLOW_VERSION = "26.0"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ExecutionHistoryEvent(BaseModel):
    ts: str = Field(default_factory=_utc_now_iso)
    node: str = ""
    event: str = ""  # started | completed | failed | skipped | resume | rerun
    detail: str = ""
    error: str | None = None


class WorkflowMemory(BaseModel):
    """Centralized orchestration index persisted as memory.json."""

    project_id: str = ""
    workflow_version: str = WORKFLOW_VERSION
    current_step: str = ""
    completed_steps: list[str] = Field(default_factory=list)
    failed_steps: list[str] = Field(default_factory=list)
    agent_outputs: dict[str, Any] = Field(default_factory=dict)
    timestamps: dict[str, str] = Field(default_factory=dict)
    status: str = "pending"
    error: str | None = None
    thread_id: str = ""
    last_node: str = ""
    last_stage: str = ""
    retry_counts: dict[str, int] = Field(default_factory=dict)
    job: dict[str, Any] = Field(default_factory=dict)
    project_dir: str = ""
    created_at: str = Field(default_factory=_utc_now_iso)
    updated_at: str = Field(default_factory=_utc_now_iso)
