"""Creator OS stage rail for the Streamlit AI Creator Platform."""

from __future__ import annotations

from typing import Any

import streamlit as st

from schemas.creator_os import CREATOR_OS_STAGES, stage_progress_from_state
from schemas.job import ProgressStepStatus


def _icon(status: str) -> str:
    if status == ProgressStepStatus.COMPLETED.value:
        return "✅"
    if status == ProgressStepStatus.RUNNING.value:
        return "🔵"
    if status == ProgressStepStatus.FAILED.value:
        return "❌"
    if status == ProgressStepStatus.SKIPPED.value:
        return "⊘"
    return "⚪"


def render_creator_os_rail(state: dict[str, Any] | None = None) -> None:
    """Render the Research → … → Analytics stage checklist."""
    stages = stage_progress_from_state(state)
    if not stages:
        stages = [
            {"id": sid, "label": label, "status": ProgressStepStatus.PENDING.value}
            for sid, label in CREATOR_OS_STAGES
        ]

    completed = sum(
        1 for s in stages if s.get("status") == ProgressStepStatus.COMPLETED.value
    )
    total = len(stages) or 1
    st.markdown("##### Creator OS stages")
    st.progress(completed / total, text=f"{completed} / {total} stages")

    cols = st.columns(min(4, total))
    for i, stage in enumerate(stages):
        with cols[i % len(cols)]:
            icon = _icon(str(stage.get("status") or "pending"))
            st.markdown(f"{icon} **{stage.get('label', '')}**")
            st.caption(str(stage.get("status") or "pending"))
