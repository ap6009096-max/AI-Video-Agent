"""Main Graph supervisor — nests six pipeline subgraphs around the flat agent graph.

Pipeline subgraphs mark Creator OS boundaries. The nested ``agent_graph`` is the
existing flat LangGraph (all agents preserved) sharing the same checkpointer /
thread_id for resume.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from core.logging import get_logger
from graph.pipelines.content_pipeline import build_content_pipeline
from graph.pipelines.growth_pipeline import build_growth_pipeline
from graph.pipelines.input_pipeline import build_input_pipeline
from graph.pipelines.localization_pipeline import build_localization_pipeline
from graph.pipelines.analysis_pipeline import build_analysis_pipeline
from graph.pipelines.rendering_pipeline import build_rendering_pipeline

logger = get_logger(__name__)


def build_main_graph(checkpointer: Any = None, *, flat_graph: Any = None):
    """Build Main → 6 pipelines → nested flat agent graph → END."""
    from graph.workflow import WorkflowState, build_flat_video_graph

    flat = flat_graph or build_flat_video_graph(checkpointer=checkpointer)

    # Marker subgraphs are ephemeral (no checkpointer) to avoid thread conflicts
    g = StateGraph(WorkflowState)
    g.add_node("input_pipeline", build_input_pipeline(WorkflowState))
    g.add_node("analysis_pipeline", build_analysis_pipeline(WorkflowState))
    g.add_node("content_pipeline", build_content_pipeline(WorkflowState))
    g.add_node("localization_pipeline", build_localization_pipeline(WorkflowState))
    g.add_node("render_pipeline", build_rendering_pipeline(WorkflowState))
    g.add_node("growth_pipeline", build_growth_pipeline(WorkflowState))
    g.add_node("agent_graph", flat)

    g.add_edge(START, "input_pipeline")
    g.add_edge("input_pipeline", "analysis_pipeline")
    g.add_edge("analysis_pipeline", "content_pipeline")
    g.add_edge("content_pipeline", "localization_pipeline")
    g.add_edge("localization_pipeline", "render_pipeline")
    g.add_edge("render_pipeline", "growth_pipeline")
    g.add_edge("growth_pipeline", "agent_graph")
    g.add_edge("agent_graph", END)

    logger.info("Compiled MainGraph with 6 pipelines + nested agent_graph")
    return g.compile(checkpointer=checkpointer)
