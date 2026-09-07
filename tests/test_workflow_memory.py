"""Tests for Prompt 26 workflow memory store."""

from __future__ import annotations

from pathlib import Path

import pytest

from config.settings import get_settings
from core.errors import WorkflowError
from core.workflow_memory import (
    append_history,
    assert_compatible_version,
    clear_from_step,
    list_resumable_projects,
    load_memory,
    new_memory,
    read_history,
    save_memory,
    update_from_workflow_state,
)
from schemas.base import JobStatus
from schemas.job import ProgressStepStatus, initial_progress_steps
from schemas.memory import WORKFLOW_VERSION, ExecutionHistoryEvent, WorkflowMemory


@pytest.fixture()
def out_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "outputs"
    monkeypatch.setenv("OUTPUT_DIR", str(root))
    get_settings.cache_clear()
    return root


def test_save_load_memory_shape(out_dir: Path) -> None:
    mem = new_memory("p26a", job={"job_id": "p26a"}, project_dir=str(out_dir / "projects" / "p26a"))
    mem.current_step = "smart_clip"
    mem.completed_steps = ["Input Validated"]
    mem.agent_outputs["clips"] = {"path": "/tmp/clips.json", "present": True}
    mem.status = JobStatus.RUNNING.value
    path = save_memory(mem)
    assert path.is_file()
    assert path.name == "memory.json"

    loaded = load_memory("p26a")
    assert loaded is not None
    assert loaded.project_id == "p26a"
    assert loaded.thread_id == "p26a"
    assert loaded.workflow_version == WORKFLOW_VERSION
    assert loaded.current_step == "smart_clip"
    assert loaded.completed_steps == ["Input Validated"]
    assert loaded.agent_outputs["clips"]["present"] is True


def test_append_and_read_history(out_dir: Path) -> None:
    append_history(
        "hist1",
        ExecutionHistoryEvent(node="input_agent", event="started", detail="go"),
    )
    append_history(
        "hist1",
        {"node": "smart_clip", "event": "completed", "detail": "ok"},
    )
    events = read_history("hist1")
    assert len(events) == 2
    assert events[0].node == "input_agent"
    assert events[1].event == "completed"
    hist_path = out_dir / "projects" / "hist1" / "execution_history.jsonl"
    assert hist_path.is_file()


def test_update_from_workflow_state_indexes_outputs(out_dir: Path) -> None:
    project_dir = out_dir / "projects" / "upd1"
    project_dir.mkdir(parents=True)
    analysis = project_dir / "analysis"
    analysis.mkdir()
    clips = analysis / "clips.json"
    clips.write_text('{"clips": []}', encoding="utf-8")

    steps = [dict(s) for s in initial_progress_steps()]
    steps[0]["status"] = ProgressStepStatus.COMPLETED.value
    steps[1]["status"] = ProgressStepStatus.RUNNING.value

    state = {
        "job": {"job_id": "upd1"},
        "project": {"project_id": "upd1"},
        "project_dir": str(project_dir),
        "status": JobStatus.RUNNING.value,
        "steps": steps,
        "current_step": 1,
        "clips": {"plan": {"skipped": False}, "clips": []},
        "error": None,
    }
    mem = update_from_workflow_state(state, last_node="smart_clip")
    assert mem.project_id == "upd1"
    assert "Input Validated" in mem.completed_steps or mem.completed_steps
    assert mem.agent_outputs.get("clips", {}).get("present") is True
    assert mem.last_node == "smart_clip"
    assert "smart_clip" in mem.timestamps


def test_clear_from_step_drops_downstream(out_dir: Path) -> None:
    mem = WorkflowMemory(
        project_id="clr1",
        thread_id="clr1",
        completed_steps=["smart_clip", "story", "script"],
        failed_steps=[],
        agent_outputs={
            "clips": {"present": True},
            "stories": {"present": True},
            "scripts": {"present": True},
            "render_pack": {"present": True},
        },
        timestamps={
            "smart_clip": "t1",
            "story": "t2",
            "script": "t3",
            "render": "t4",
        },
        status=JobStatus.FAILED.value,
        error="boom",
    )
    cleared = clear_from_step(mem, "story")
    assert cleared.current_step == "story"
    assert cleared.status == JobStatus.RUNNING.value
    assert cleared.error is None
    assert "story" not in cleared.timestamps
    assert "script" not in cleared.timestamps
    assert "render" not in cleared.timestamps
    assert "smart_clip" in cleared.timestamps
    assert "clips" in cleared.agent_outputs
    assert "stories" not in cleared.agent_outputs
    assert "scripts" not in cleared.agent_outputs
    assert "render_pack" not in cleared.agent_outputs


def test_version_mismatch_refuses_resume(out_dir: Path) -> None:
    mem = WorkflowMemory(
        project_id="ver1",
        thread_id="ver1",
        workflow_version="1.0",
    )
    with pytest.raises(WorkflowError, match="version mismatch"):
        assert_compatible_version(mem)


def test_list_resumable_skips_completed(out_dir: Path) -> None:
    a = new_memory("ra", job={"job_id": "ra"})
    a.status = JobStatus.RUNNING.value
    save_memory(a)
    b = new_memory("rb", job={"job_id": "rb"})
    b.status = JobStatus.COMPLETED.value
    save_memory(b)
    c = new_memory("rc", job={"job_id": "rc"})
    c.status = JobStatus.FAILED.value
    save_memory(c)

    found = list_resumable_projects()
    ids = {m.project_id for m in found}
    assert "ra" in ids
    assert "rc" in ids
    assert "rb" not in ids
