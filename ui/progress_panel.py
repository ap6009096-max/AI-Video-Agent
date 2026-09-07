"""Progress panel for Creator OS stages + fine-grained pipeline steps."""

from __future__ import annotations

from typing import Any

import streamlit as st

from schemas.base import JobStatus
from schemas.creator_os import stage_progress_from_state
from schemas.job import PIPELINE_STEPS, ProgressStepStatus, initial_progress_steps
from ui.creator_os import render_creator_os_rail


def init_progress_session() -> None:
    """Ensure session state keys used by the progress panel exist."""
    if "pipeline_steps" not in st.session_state:
        st.session_state.pipeline_steps = initial_progress_steps()
    if "pipeline_status" not in st.session_state:
        st.session_state.pipeline_status = JobStatus.PENDING.value
    if "last_result" not in st.session_state:
        st.session_state.last_result = None
    if "pipeline_error" not in st.session_state:
        st.session_state.pipeline_error = None
    if "pipeline_messages" not in st.session_state:
        st.session_state.pipeline_messages = []
    if "workflow_state_snapshot" not in st.session_state:
        st.session_state.workflow_state_snapshot = {}


def update_progress_from_state(state: dict[str, Any]) -> None:
    """Copy workflow state into Streamlit session for the progress panel."""
    st.session_state.pipeline_steps = state.get("steps", initial_progress_steps())
    st.session_state.pipeline_status = state.get("status", JobStatus.PENDING.value)
    st.session_state.pipeline_error = state.get("error")
    st.session_state.pipeline_messages = state.get("messages", [])
    st.session_state.workflow_state_snapshot = dict(state)
    if state.get("result") is not None:
        st.session_state.last_result = state.get("result")


def _step_icon(status: str) -> str:
    if status == ProgressStepStatus.COMPLETED.value:
        return "✅"
    if status == ProgressStepStatus.RUNNING.value:
        return "🔵"
    if status == ProgressStepStatus.FAILED.value:
        return "❌"
    return "⚪"


def _step_css_class(status: str) -> str:
    return f"ava-step-{status}"


def render_progress_panel() -> None:
    """Render Creator OS stages (primary) and fine-grained steps (secondary)."""
    init_progress_session()
    st.subheader("Progress")

    snapshot = st.session_state.get("workflow_state_snapshot") or {}
    if not snapshot and st.session_state.last_result:
        snapshot = dict(st.session_state.last_result)
        snapshot["status"] = st.session_state.pipeline_status
        snapshot["steps"] = st.session_state.pipeline_steps
        snapshot["error"] = st.session_state.pipeline_error
        snapshot["messages"] = st.session_state.pipeline_messages

    # Ensure status mirrors session for stage derivation mid-run
    if snapshot:
        snapshot = {
            **snapshot,
            "status": st.session_state.pipeline_status,
            "steps": st.session_state.pipeline_steps,
            "error": st.session_state.pipeline_error,
            "messages": st.session_state.pipeline_messages,
        }
    else:
        snapshot = {
            "status": st.session_state.pipeline_status,
            "steps": st.session_state.pipeline_steps,
            "error": st.session_state.pipeline_error,
            "messages": st.session_state.pipeline_messages,
        }

    render_creator_os_rail(snapshot)

    steps: list[dict[str, Any]] = st.session_state.pipeline_steps
    status = st.session_state.pipeline_status
    total = len(PIPELINE_STEPS) or 15
    completed = sum(
        1 for s in steps if s.get("status") == ProgressStepStatus.COMPLETED.value
    )
    fraction = completed / total if total else 0.0

    with st.expander("Fine-grained pipeline steps", expanded=False):
        st.progress(fraction, text=f"{completed} / {total} steps · status: {status}")
        lines: list[str] = ['<div class="ava-progress-card">']
        for step in steps:
            step_status = step.get("status", ProgressStepStatus.PENDING.value)
            icon = _step_icon(step_status)
            css = _step_css_class(step_status)
            label = step.get("label", "")
            idx = step.get("id", 0) + 1
            lines.append(f'<div class="{css}">{icon} {idx}. {label}</div>')
        lines.append("</div>")
        st.markdown("\n".join(lines), unsafe_allow_html=True)

    if st.session_state.pipeline_error:
        st.error(st.session_state.pipeline_error)

    # Stage summary caption
    stage_rows = stage_progress_from_state(snapshot)
    running = next(
        (s for s in stage_rows if s.get("status") == ProgressStepStatus.RUNNING.value),
        None,
    )
    if running:
        st.caption(f"Current stage: **{running.get('label')}**")

    if status == JobStatus.COMPLETED.value:
        st.success("Creator OS run finished — multi-platform package ready.")
        if st.session_state.last_result:
            from ui.results_panel import render_results_panel

            render_results_panel(st.session_state.last_result)
            with st.expander("Raw result JSON"):
                st.json(st.session_state.last_result)
        if st.session_state.pipeline_messages:
            with st.expander("Pipeline messages"):
                for msg in st.session_state.pipeline_messages:
                    st.write(f"- {msg}")
    elif status == JobStatus.FAILED.value and st.session_state.last_result:
        from ui.results_panel import render_results_panel

        render_results_panel(st.session_state.last_result)
