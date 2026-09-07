"""Tests for Prompt 26 checkpoint resume / partial rerun."""

from __future__ import annotations

from pathlib import Path

import pytest
from langgraph.checkpoint.memory import MemorySaver

from agents.story_agent import StoryAgent
from config.settings import get_settings
from core.errors import StoryAgentError, WorkflowError
from core.workflow_memory import clear_from_step, load_memory, read_history, save_memory
from graph.agent_bus import publish_output, read_output
from graph.workflow import run_video_workflow
from schemas.base import JobStatus
from schemas.job import SourceType, VideoJobRequest
from schemas.memory import WORKFLOW_VERSION, WorkflowMemory
from schemas.story import GeminiClipStory, GeminiStoriesBatch
from tests.test_workflow import (
    _install_mock_language_agent,
    _install_mock_story_script_agents,
    _install_mock_text_agent,
)


@pytest.fixture()
def out_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "outputs"
    monkeypatch.setenv("OUTPUT_DIR", str(root))
    get_settings.cache_clear()
    return root


def _script_request(job_id: str = "resume-job") -> VideoJobRequest:
    return VideoJobRequest(
        job_id=job_id,
        source_type=SourceType.SCRIPT,
        script_text="Resume test script. Second sentence here.",
    )


def test_fresh_run_persists_memory_and_history(
    out_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_mock_text_agent(monkeypatch)
    _install_mock_story_script_agents(monkeypatch)
    _install_mock_language_agent(monkeypatch)

    saver = MemorySaver()
    result = run_video_workflow(
        _script_request("mem-persist"),
        checkpointer=saver,
    )
    assert result["status"] == JobStatus.COMPLETED.value

    mem = load_memory("mem-persist")
    assert mem is not None
    assert mem.workflow_version == WORKFLOW_VERSION
    assert mem.thread_id == "mem-persist"
    assert mem.status == JobStatus.COMPLETED.value
    assert mem.agent_outputs  # indexed packs
    hist = read_history("mem-persist")
    assert len(hist) >= 1
    assert (out_dir / "projects" / "mem-persist" / "memory.json").is_file()


def test_resume_version_mismatch_raises(out_dir: Path) -> None:
    mem = WorkflowMemory(
        project_id="badver",
        thread_id="badver",
        workflow_version="0.1",
        status=JobStatus.RUNNING.value,
        job=_script_request("badver").model_dump(mode="json"),
    )
    save_memory(mem)
    with pytest.raises(WorkflowError, match="version mismatch"):
        run_video_workflow(
            _script_request("badver"),
            resume=True,
            project_id="badver",
            checkpointer=MemorySaver(),
        )


def test_resume_without_memory_raises(out_dir: Path) -> None:
    with pytest.raises(WorkflowError, match="No memory.json"):
        run_video_workflow(
            _script_request("missing"),
            resume=True,
            project_id="missing",
            checkpointer=MemorySaver(),
        )


def test_from_step_clears_downstream_in_memory(
    out_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_mock_text_agent(monkeypatch)
    _install_mock_story_script_agents(monkeypatch)
    _install_mock_language_agent(monkeypatch)

    saver = MemorySaver()
    run_video_workflow(_script_request("partial1"), checkpointer=saver)

    mem = load_memory("partial1")
    assert mem is not None
    mem.agent_outputs["stories"] = {"present": True}
    mem.agent_outputs["scripts"] = {"present": True}
    mem.agent_outputs["render_pack"] = {"present": True}
    mem.timestamps["story"] = "t"
    mem.timestamps["script"] = "t"
    mem.timestamps["render"] = "t"
    mem.status = JobStatus.COMPLETED.value
    save_memory(mem)

    cleared = clear_from_step(load_memory("partial1"), "story")  # type: ignore[arg-type]
    assert "stories" not in cleared.agent_outputs
    assert "scripts" not in cleared.agent_outputs
    assert "render_pack" not in cleared.agent_outputs
    assert cleared.current_step == "story"


def test_resume_from_checkpoint_completes(
    out_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fail once at story, then resume with the same MemorySaver thread."""
    _install_mock_text_agent(monkeypatch)
    _install_mock_language_agent(monkeypatch)
    _install_mock_story_script_agents(monkeypatch)

    saver = MemorySaver()
    call_count = {"n": 0}

    def _stories(clip_blocks, **_kwargs) -> GeminiStoriesBatch:
        return GeminiStoriesBatch(
            stories=[
                GeminiClipStory(
                    clip_id=0,
                    hook="Hook from source",
                    context="Brief context",
                    value_event="Core value from clip",
                    payoff="Clear payoff",
                    cta="Follow for more",
                )
            ]
        )

    def _flaky_story_factory():
        agent = StoryAgent(generate_fn=_stories)
        orig = agent.run

        def _run(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise StoryAgentError("simulated interrupt")
            return orig(*args, **kwargs)

        agent.run = _run  # type: ignore[method-assign]
        return agent

    monkeypatch.setattr("graph.workflow.StoryAgent", _flaky_story_factory)

    request = _script_request("ckpt-resume")
    with pytest.raises(WorkflowError):
        run_video_workflow(request, checkpointer=saver)

    mem = load_memory("ckpt-resume")
    assert mem is not None
    assert mem.status == JobStatus.FAILED.value

    result = run_video_workflow(
        request,
        resume=True,
        project_id="ckpt-resume",
        retry_failed=True,
        checkpointer=saver,
    )
    assert result["status"] == JobStatus.COMPLETED.value
    mem2 = load_memory("ckpt-resume")
    assert mem2 is not None
    assert mem2.status == JobStatus.COMPLETED.value
    assert call_count["n"] >= 2


def test_agent_bus_publish_read(out_dir: Path) -> None:
    publish_output("bus1", "clips", {"path": "analysis/clips.json"})
    assert read_output("bus1", "clips") == {"path": "analysis/clips.json"}
    assert read_output("bus1", "missing") is None
