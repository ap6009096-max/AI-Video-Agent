"""Streamlit UI building blocks for the video creation studio.

Eager imports are avoided so Streamlit Cloud can boot without loading the
full LangGraph / agents / YouTube ingestion stack up front.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "apply_styles",
    "init_progress_session",
    "merge_creator_os_preset",
    "render_config_form",
    "render_creator_os_rail",
    "render_feature_toggles",
    "render_progress_panel",
    "render_results_panel",
    "render_resume_controls",
    "render_source_form",
    "run_job_from_ui",
]

_LAZY_ATTRS: dict[str, tuple[str, str]] = {
    "apply_styles": ("ui.styles", "apply_styles"),
    "init_progress_session": ("ui.progress_panel", "init_progress_session"),
    "merge_creator_os_preset": ("ui.feature_toggles", "merge_creator_os_preset"),
    "render_config_form": ("ui.config_form", "render_config_form"),
    "render_creator_os_rail": ("ui.creator_os", "render_creator_os_rail"),
    "render_feature_toggles": ("ui.feature_toggles", "render_feature_toggles"),
    "render_progress_panel": ("ui.progress_panel", "render_progress_panel"),
    "render_results_panel": ("ui.results_panel", "render_results_panel"),
    "render_resume_controls": ("ui.resume_panel", "render_resume_controls"),
    "render_source_form": ("ui.source_form", "render_source_form"),
    "run_job_from_ui": ("ui.job_runner", "run_job_from_ui"),
}


def __getattr__(name: str) -> Any:
    target = _LAZY_ATTRS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr = target
    from importlib import import_module

    value = getattr(import_module(module_name), attr)
    globals()[name] = value
    return value
