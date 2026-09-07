"""Tests for supervisor crew graph helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from agents.supervisor_agent import SupervisorAgent
from config.settings import get_settings
from graph.supervisor_crew import (
    route_supervisor_next,
    run_crew_story,
    run_supervisor_turn,
)
from schemas.base import JobStatus
from schemas.job import SourceType
from schemas.project import ProjectMetadata
from schemas.supervisor import GeminiSupervisorDecision


def test_route_supervisor_next_maps_workers() -> None:
    assert route_supervisor_next({"next_agent": "story", "status": "running"}) == "story"
    assert route_supervisor_next({"next_agent": "FINISH", "status": "running"}) == "FINISH"
    assert (
        route_supervisor_next({"status": JobStatus.FAILED.value, "error": "x"})
        == "crew_failed"
    )


def test_run_supervisor_turn_writes_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "c1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="c1", source_type=SourceType.SCRIPT, raw_text="Hello topic"
    ).model_dump(mode="json")

    monkeypatch.setattr(
        "graph.supervisor_crew.SupervisorAgent",
        lambda: SupervisorAgent(
            decide_fn=lambda **_k: GeminiSupervisorDecision(
                next_agent="story", task="stories", reason="test", done=False
            )
        ),
    )
    out = run_supervisor_turn(
        {
            "project": project,
            "project_dir": str(project_dir),
            "crew_step": 0,
            "messages": [],
            "status": JobStatus.RUNNING.value,
        }
    )
    assert out["next_agent"] == "story"
    assert out["supervisor_crew"] is not None
    assert (project_dir / "analysis" / "supervisor_crew.json").is_file()
    assert any("supervisor → story" in m for m in out["messages"])
    get_settings.cache_clear()


def test_crew_story_worker_reports_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "c2"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="c2", source_type=SourceType.SCRIPT, raw_text="Hello"
    ).model_dump(mode="json")

    class _FakeStory:
        def run(self, *args, **kwargs):
            from schemas.story import StoriesReport, StoryAgentResult

            report = StoriesReport(
                project_id="c2",
                stories=[],
                provider="test",
                notes="empty",
            )
            path = project_dir / "analysis" / "stories.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}", encoding="utf-8")
            return StoryAgentResult(
                stories=report,
                stories_path=str(path),
                messages=["[story] ok"],
            )

    monkeypatch.setattr("graph.supervisor_crew.StoryAgent", lambda: _FakeStory())
    state = {
        "project": project,
        "project_dir": str(project_dir),
        "job": {"config": {}, "features": {}},
        "clips": {"clips": []},
        "supervisor_crew": {
            "project_id": "c2",
            "decisions": [],
            "delegation_log": [],
            "task_board": [],
            "retry_counts": {},
            "finished": False,
            "provider": "supervisor",
            "notes": "",
            "skipped": False,
        },
        "messages": [],
        "status": JobStatus.RUNNING.value,
    }
    out = run_crew_story(state)
    assert any("story → supervisor" in m for m in out["messages"])
    assert out["stories"] is not None
    get_settings.cache_clear()
