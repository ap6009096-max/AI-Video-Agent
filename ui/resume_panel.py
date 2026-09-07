"""Resume / partial-rerun controls for Prompt 26 memory."""

from __future__ import annotations

from typing import Any

import streamlit as st

from core.workflow_memory import list_resumable_projects
from schemas.job import PIPELINE_STEPS


def render_resume_controls() -> dict[str, Any]:
    """Render resume / rerun controls; return options for the job runner."""
    st.subheader("Memory & Resume")
    resumable = list_resumable_projects()
    options = ["(new job)"] + [
        f"{m.project_id} · {m.status} · {m.current_step or m.last_node or '—'}"
        for m in resumable
    ]
    choice = st.selectbox("Resume project", options, index=0)
    resume = choice != "(new job)"
    project_id = ""
    if resume:
        idx = options.index(choice) - 1
        project_id = resumable[idx].project_id
        st.caption(
            f"Will resume `{project_id}` "
            f"(version={resumable[idx].workflow_version}, "
            f"failed={resumable[idx].failed_steps})"
        )

    from_step = None
    retry_failed = False
    if resume and project_id:
        mem = resumable[options.index(choice) - 1]
        step_choices = ["(continue from checkpoint)"] + list(PIPELINE_STEPS)
        # Also allow graph node names present in timestamps
        for node in sorted(mem.timestamps.keys()):
            if node.startswith("_"):
                continue
            if node not in step_choices:
                step_choices.append(node)
        selected = st.selectbox("Rerun from step", step_choices, index=0)
        if selected != "(continue from checkpoint)":
            from_step = selected
        retry_failed = st.checkbox(
            "Retry failed steps (max 1)",
            value=bool(mem.failed_steps),
        )

    return {
        "resume": resume,
        "project_id": project_id,
        "from_step": from_step,
        "retry_failed": retry_failed,
    }
