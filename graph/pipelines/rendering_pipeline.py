"""Rendering pipeline subgraph."""

from __future__ import annotations

from typing import Any

from graph.pipelines.runner import build_marker_subgraph


def build_rendering_pipeline(state_schema: type, checkpointer: Any = None):
    return build_marker_subgraph(
        "render_pipeline", state_schema=state_schema, checkpointer=checkpointer
    )
