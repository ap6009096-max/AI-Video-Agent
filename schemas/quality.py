"""Quality control schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class QualityCheck(BaseModel):
    id: str = ""
    passed: bool = False
    expected: str = ""
    actual: str = ""
    message: str = ""


class QualityReport(BaseModel):
    project_id: str = ""
    media_path: str = ""
    checks: list[QualityCheck] = Field(default_factory=list)
    passed: bool = False
    corrections_attempted: list[str] = Field(default_factory=list)
    rerender_requested: bool = False
    skipped: bool = False
    notes: str = ""
    created_at: datetime = Field(default_factory=_utc_now)


class QualityPack(BaseModel):
    report: QualityReport = Field(default_factory=QualityReport)
    notes: str = ""
    created_at: datetime = Field(default_factory=_utc_now)


class QualityResult(BaseModel):
    quality_pack: QualityPack
    quality_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "quality_pack": self.quality_pack.model_dump(mode="json"),
            "messages": list(self.messages),
        }
