"""Lightweight agent output bus backed by workflow memory."""

from __future__ import annotations

from typing import Any

from core.workflow_memory import load_memory, save_memory
from schemas.memory import WorkflowMemory


def publish_output(
    project_id: str,
    agent: str,
    payload_ref: Any,
    *,
    output_dir: str | None = None,
) -> WorkflowMemory | None:
    """Record an agent output reference in memory.agent_outputs."""
    memory = load_memory(project_id, output_dir)
    if memory is None:
        memory = WorkflowMemory(project_id=project_id, thread_id=project_id)
    memory.agent_outputs[agent] = payload_ref
    save_memory(memory, output_dir)
    return memory


def read_output(
    project_id: str,
    agent: str,
    *,
    output_dir: str | None = None,
) -> Any | None:
    memory = load_memory(project_id, output_dir)
    if memory is None:
        return None
    return memory.agent_outputs.get(agent)
