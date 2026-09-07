"""Build a compiled pipeline subgraph wrapping existing node callables."""

from __future__ import annotations

from typing import Any, Callable

from langgraph.graph import END, START, StateGraph

from graph.pipelines import pipeline_hook


def build_marker_subgraph(
    name: str,
    *,
    state_schema: type,
    checkpointer: Any = None,
    extra_nodes: list[tuple[str, Callable[..., Any]]] | None = None,
):
    """Compile a small subgraph: START → marker → optional extras → END."""
    g = StateGraph(state_schema)
    g.add_node(name, pipeline_hook(name))
    prev = name
    for node_name, fn in extra_nodes or []:
        g.add_node(node_name, fn)
        g.add_edge(prev, node_name)
        prev = node_name
    g.add_edge(START, name)
    g.add_edge(prev, END)
    return g.compile(checkpointer=checkpointer)
