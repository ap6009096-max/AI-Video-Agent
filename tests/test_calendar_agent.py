"""Tests for ContentCalendarAgent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.calendar_agent import ContentCalendarAgent
from config.settings import get_settings
from schemas.calendar import CalendarPack, CalendarPlan, CalendarEntry
from schemas.job import FeatureFlags, SourceType, VideoJobConfig
from schemas.project import ProjectMetadata


def test_calendar_flag_off_skips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "cal1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="cal1", source_type=SourceType.SCRIPT, raw_text="x"
    )
    result = ContentCalendarAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(platform="YouTube"),
        features=FeatureFlags(content_calendar=False),
    )
    assert result.calendar_pack.plan.skipped is True
    data = json.loads(Path(result.calendar_path).read_text(encoding="utf-8"))
    assert data["plan"]["skipped"] is True
    assert data["plan"]["entries"] == []
    get_settings.cache_clear()


def test_calendar_writes_json_when_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "cal2"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="cal2", source_type=SourceType.YOUTUBE, source_path="https://x"
    )

    def _build(**_: object) -> CalendarPack:
        return CalendarPack(
            source_label="YouTube",
            plan=CalendarPlan(
                entries=[
                    CalendarEntry(
                        date="2026-09-01",
                        topic="Hook tips",
                        platform="YouTube",
                        video_type="Shorts",
                    )
                ],
                daily=[],
                weekly=[],
                monthly=[],
                horizon_days=30,
                anchor_date="2026-09-01",
                platform="YouTube",
                video_type="Shorts",
                provider="heuristic",
                skipped=False,
                notes="test pack",
            ),
            notes="test pack",
        )

    result = ContentCalendarAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(platform="YouTube", video_type="Shorts"),
        features=FeatureFlags(content_calendar=True),
        script_pack={"primary": {"title": "Hooks"}},
        build_fn=_build,
    )
    assert result.calendar_pack.plan.skipped is False
    path = Path(result.calendar_path)
    assert path.name == "calendar_plan.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["plan"]["entries"][0]["topic"] == "Hook tips"
    public = result.public_output()
    assert "entries" in public
    assert "daily" in public
    assert "weekly" in public
    assert "monthly" in public
    get_settings.cache_clear()
