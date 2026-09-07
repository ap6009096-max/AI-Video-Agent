"""Analysis pipeline subgraph (+ shared AI / objects hooks)."""

from __future__ import annotations

from typing import Any

from graph.pipelines.runner import build_marker_subgraph


def build_analysis_pipeline(
    state_schema: type,
    checkpointer: Any = None,
    *,
    shared_ai_node: Any = None,
    objects_node: Any = None,
):
    extras: list[tuple[str, Any]] = []
    if shared_ai_node is not None:
        extras.append(("shared_ai_analysis", shared_ai_node))
    if objects_node is not None:
        extras.append(("object_detection", objects_node))
    return build_marker_subgraph(
        "analysis_pipeline",
        state_schema=state_schema,
        checkpointer=checkpointer,
        extra_nodes=extras or None,
    )
