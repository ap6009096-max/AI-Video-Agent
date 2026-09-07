"""Growth pipeline subgraph (+ competitor hook)."""

from __future__ import annotations

from typing import Any

from graph.pipelines.runner import build_marker_subgraph


def build_growth_pipeline(
    state_schema: type,
    checkpointer: Any = None,
    *,
    competitor_node: Any = None,
):
    extras = []
    if competitor_node is not None:
        extras.append(("competitor", competitor_node))
    return build_marker_subgraph(
        "growth_pipeline",
        state_schema=state_schema,
        checkpointer=checkpointer,
        extra_nodes=extras or None,
    )
