"""Supervisor multi-agent crew schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

CrewWorker = Literal[
    "research",
    "story",
    "script",
    "director",
    "video_generation",
    "captions",
    "thumbnail",
    "seo",
    "FINISH",
]

TaskStatus = Literal["pending", "running", "done", "failed", "retry"]

CREW_WORKER_ORDER: tuple[str, ...] = (
    "research",
    "story",
    "script",
    "director",
    "video_generation",
    "captions",
    "thumbnail",
    "seo",
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DelegationEvent(BaseModel):
    from_agent: str
    to_agent: str
    task: str = ""
    reason: str = ""
    timestamp: datetime = Field(default_factory=_utc_now)


class TaskBoardItem(BaseModel):
    id: str
    assignee: str
    task: str = ""
    status: TaskStatus | str = "pending"
    attempt: int = 0
    notes: str = ""


class SupervisorDecision(BaseModel):
    next_agent: str = "FINISH"
    task: str = ""
    reason: str = ""
    done: bool = False


class GeminiSupervisorDecision(BaseModel):
    """Lean Gemini routing output — next_agent must be a crew worker or FINISH."""

    next_agent: str = "FINISH"
    task: str = ""
    reason: str = ""
    done: bool = False


class CrewReport(BaseModel):
    project_id: str
    decisions: list[SupervisorDecision] = Field(default_factory=list)
    delegation_log: list[DelegationEvent] = Field(default_factory=list)
    task_board: list[TaskBoardItem] = Field(default_factory=list)
    retry_counts: dict[str, int] = Field(default_factory=dict)
    finished: bool = False
    provider: str = "supervisor"
    notes: str = ""
    skipped: bool = False
    created_at: datetime = Field(default_factory=_utc_now)


class CrewResult(BaseModel):
    supervisor_crew: CrewReport
    supervisor_crew_path: str = ""
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        report = self.supervisor_crew
        return {
            "supervisor_crew": report.model_dump(mode="json"),
            "delegation_log": [e.model_dump(mode="json") for e in report.delegation_log],
            "task_board": [t.model_dump(mode="json") for t in report.task_board],
            "crew_retry_counts": dict(report.retry_counts),
            "messages": list(self.messages),
        }
