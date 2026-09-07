"""Prompt templates for the provider-agnostic Video Generation Agent."""

from __future__ import annotations

VIDEO_GENERATION_AGENT_SYSTEM = """You are a video generation planner for short-form and long-form content.

Given script, optional storyboard, visual style, environment, and a generation mode
(Cinematic / Animation / Documentary / Explainer / AI Avatar / Motion Graphics),
produce a provider-agnostic video generation plan.

For each shot return:
- scene (1-based int)
- duration (seconds, typically 2–8)
- prompt (full scene prompt suitable for ANY video model)
- visual_style
- environment
- camera_move
- shot_type
- transition
- voiceover

Rules:
- Do NOT name or target a specific vendor (Runway, Pika, Luma, Veo, etc.).
- Prompts must be portable and concrete.
- Prefer storyboard timing/camera when provided.
- Keep the list concise (max ~12 shots).
"""


def build_video_generation_agent_user_prompt(
    *,
    mode: str,
    style: str,
    environment: str,
    audience: str,
    title: str,
    hook: str,
    script_block: str,
    storyboard_block: str,
    mode_suffix: str,
    camera_vocab: str,
) -> str:
    return (
        f"Generation mode: {mode or 'Cinematic'}\n"
        f"Visual style: {style or '(none)'}\n"
        f"Environment: {environment or '(none)'}\n"
        f"Audience: {audience or 'General'}\n\n"
        f"Title: {title or '(none)'}\n"
        f"Hook: {hook or '(none)'}\n\n"
        f"## Mode prompt guidance\n{mode_suffix or '(none)'}\n\n"
        f"## Camera move vocabulary\n{camera_vocab or '(none)'}\n\n"
        f"## Script\n{script_block or '(none)'}\n\n"
        f"## Storyboard (if any)\n{storyboard_block or '(none)'}\n\n"
        "Return shots with scene, duration, prompt, visual_style, environment, "
        "camera_move, shot_type, transition, voiceover. "
        "Keep the plan provider-agnostic."
    )
