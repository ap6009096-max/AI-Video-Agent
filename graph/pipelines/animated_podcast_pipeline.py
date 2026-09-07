"""Animated Podcast Sub-pipeline — orchestration helper for Animated Podcast mode.

Activated when output_mode == "animated_podcast".
Pipeline:
  Podcast Media / Transcript
        ↓
  Content Classification
        ↓
  Animation Plan (per-scene JSON visual specs)
        ↓
  Voice Generation (dialogue TTS)
        ↓
  Caption Generation (subtitles/overlays)
        ↓
  Smart Reframing & Composition
        ↓
  FFmpeg Render
"""

from __future__ import annotations

from typing import Any

from agents.animation_plan_agent import AnimationPlanAgent
from agents.content_classifier_agent import ContentClassifierAgent
from core.logging import get_logger

logger = get_logger(__name__)


def run_animated_podcast_pipeline(state: dict[str, Any]) -> dict[str, Any]:
    """Execute animation plan steps for an animated podcast project."""
    project = state.get("project") or {}
    project_dir = state.get("project_dir")
    transcript = state.get("transcript")
    speech_transcript = state.get("speech_transcript")
    speakers = state.get("speakers")
    scenes = state.get("scenes")
    funny_moments = state.get("funny_moments")

    # 1. Content classification
    classifier = ContentClassifierAgent()
    class_res = classifier.run(
        project,
        project_dir=project_dir,
        transcript=transcript,
        speech_transcript=speech_transcript,
        speakers=speakers,
        scenes=scenes,
    )

    # 2. Animation planning
    planner = AnimationPlanAgent()
    plan_res = planner.run(
        project,
        project_dir=project_dir,
        transcript=transcript,
        speech_transcript=speech_transcript,
        speakers=speakers,
        scenes=scenes,
        content_classification=class_res.get("content_classification"),
        funny_moments=funny_moments,
    )

    messages = (
        (state.get("messages") or [])
        + class_res.get("messages", [])
        + plan_res.get("messages", [])
    )

    return {
        **state,
        "content_classification": class_res.get("content_classification"),
        "animation_plan": plan_res.get("animation_plan"),
        "messages": messages,
    }

