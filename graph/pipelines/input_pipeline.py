"""Input pipeline subgraph."""

from __future__ import annotations

from typing import Any

from graph.pipelines.runner import build_marker_subgraph


def build_input_pipeline(state_schema: type, checkpointer: Any = None):
    return build_marker_subgraph(
        "input_pipeline", state_schema=state_schema, checkpointer=checkpointer
    )
