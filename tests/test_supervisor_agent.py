"""Tests for SupervisorAgent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.supervisor_agent import SupervisorAgent, pack_looks_complete
from config.settings import get_settings
from schemas.job import SourceType
from schemas.project import ProjectMetadata
from schemas.supervisor import GeminiSupervisorDecision, SupervisorDecision


def test_heuristic_order_and_finish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "s1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="s1", source_type=SourceType.SCRIPT, raw_text="Topic text"
    )

    agent = SupervisorAgent(decide_fn=lambda **_k: None)
    state: dict = {"crew_step": 0, "messages": []}
    result = agent.run(project, project_dir=project_dir, state=state)
    decision = result.supervisor_crew.decisions[-1]
    assert decision.next_agent == "research"
    assert decision.done is False
    assert Path(result.supervisor_crew_path).is_file()

    # Mark all packs complete → FINISH
    full = {
        "research_report": {"topic": "T", "claims": [{"text": "x"}]},
        "stories": {"stories": [{"clip_id": 0}]},
        "scripts": {"scripts": [{"clip_id": 0}]},
        "director_pack": {"plan": {"notes": "ok"}},
        "video_generation_pack": {"plan": {"notes": "ok"}},
        "captions_pack": {"plan": {"skipped": False}},
        "thumbnail_pack": {"plan": {"notes": "ok"}},
        "seo_pack": {"plan": {"notes": "ok"}},
        "supervisor_crew": result.supervisor_crew.model_dump(mode="json"),
        "crew_step": 1,
        "messages": [],
    }
    assert pack_looks_complete("research", full)
    done = agent.run(project, project_dir=project_dir, state=full)
    assert done.supervisor_crew.decisions[-1].next_agent == "FINISH"
    assert done.supervisor_crew.finished is True
    get_settings.cache_clear()


def test_gemini_inject_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "s2"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="s2", source_type=SourceType.UPLOAD, source_path="x.mp4"
    )

    def _decide(**_kwargs):
        return GeminiSupervisorDecision(
            next_agent="story",
            task="Write stories",
            reason="injected",
            done=False,
        )

    result = SupervisorAgent(decide_fn=_decide).run(
        project,
        project_dir=project_dir,
        state={"crew_step": 0, "messages": []},
    )
    assert result.supervisor_crew.decisions[-1].next_agent == "story"
    assert result.supervisor_crew.delegation_log[-1].to_agent == "story"
    get_settings.cache_clear()


def test_retry_under_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("SUPERVISOR_MAX_RETRIES", "1")
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "s3"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="s3", source_type=SourceType.SCRIPT, raw_text="x"
    )
    agent = SupervisorAgent(decide_fn=lambda **_k: None)
    first = agent.run(project, project_dir=project_dir, state={"crew_step": 0})
    report = first.supervisor_crew
    report = agent.mark_worker_result(
        report, worker="research", ok=False, notes="boom", retry_counts={}
    )
    state = {
        "supervisor_crew": report.model_dump(mode="json"),
        "crew_retry_counts": report.retry_counts,
        "crew_step": 1,
        "messages": [],
    }
    second = agent.run(project, project_dir=project_dir, state=state)
    assert second.supervisor_crew.decisions[-1].next_agent == "research"
    get_settings.cache_clear()


def test_max_steps_forces_finish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("SUPERVISOR_MAX_STEPS", "2")
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "s4"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="s4", source_type=SourceType.SCRIPT, raw_text="x"
    )
    result = SupervisorAgent(decide_fn=lambda **_k: None).run(
        project,
        project_dir=project_dir,
        state={"crew_step": 2, "messages": []},
    )
    assert result.supervisor_crew.decisions[-1].next_agent == "FINISH"
    data = json.loads(Path(result.supervisor_crew_path).read_text(encoding="utf-8"))
    assert data["finished"] is True
    get_settings.cache_clear()
