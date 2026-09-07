"""Content calendar schemas — daily / weekly / monthly schedules."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CalendarEntry(BaseModel):
    """Public calendar slot shape."""

    date: str = ""
    topic: str = ""
    platform: str = ""
    video_type: str = ""


class DailyPlan(BaseModel):
    date: str = ""
    entries: list[CalendarEntry] = Field(default_factory=list)


class WeeklySchedule(BaseModel):
    week_start: str = ""
    week_end: str = ""
    entries: list[CalendarEntry] = Field(default_factory=list)


class MonthlySchedule(BaseModel):
    month: str = ""
    entries: list[CalendarEntry] = Field(default_factory=list)


class GeminiCalendarBatch(BaseModel):
    """Optional Gemini topic enrichments (aligned to dates)."""

    topics: list[str] = Field(default_factory=list)
    notes: str = ""


class CalendarPlan(BaseModel):
    entries: list[CalendarEntry] = Field(default_factory=list)
    daily: list[DailyPlan] = Field(default_factory=list)
    weekly: list[WeeklySchedule] = Field(default_factory=list)
    monthly: list[MonthlySchedule] = Field(default_factory=list)
    horizon_days: int = 30
    anchor_date: str = ""
    platform: str = ""
    video_type: str = ""
    provider: str = "none"
    skipped: bool = False
    notes: str = ""


class CalendarPack(BaseModel):
    source_label: str = ""
    plan: CalendarPlan = Field(default_factory=CalendarPlan)
    fallback: bool = False
    notes: str = ""
    created_at: datetime = Field(default_factory=_utc_now)


class CalendarResult(BaseModel):
    calendar_pack: CalendarPack
    calendar_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "calendar_pack": self.calendar_pack.model_dump(mode="json"),
            "messages": list(self.messages),
        }

    def public_output(self) -> dict[str, Any]:
        p = self.calendar_pack.plan
        return {
            "entries": [e.model_dump() for e in p.entries],
            "daily": [d.model_dump() for d in p.daily],
            "weekly": [w.model_dump() for w in p.weekly],
            "monthly": [m.model_dump() for m in p.monthly],
        }
