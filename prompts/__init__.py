"""Prompt templates for LLM agents."""

from prompts.cultural_adaptation_agent import (
    CULTURAL_ADAPTATION_SYSTEM,
    build_cultural_adaptation_user_prompt,
)
from prompts.humor_localization_agent import (
    HUMOR_LOCALIZATION_SYSTEM,
    build_humor_localization_user_prompt,
)
from prompts.language_agent import LANGUAGE_AGENT_SYSTEM, build_language_agent_user_prompt
from prompts.script_agent import SCRIPT_AGENT_SYSTEM, build_script_agent_user_prompt
from prompts.story_agent import STORY_AGENT_SYSTEM, build_story_agent_user_prompt
from prompts.text_agent import TEXT_AGENT_SYSTEM, build_text_agent_user_prompt

__all__ = [
    "TEXT_AGENT_SYSTEM",
    "build_text_agent_user_prompt",
    "STORY_AGENT_SYSTEM",
    "build_story_agent_user_prompt",
    "SCRIPT_AGENT_SYSTEM",
    "build_script_agent_user_prompt",
    "LANGUAGE_AGENT_SYSTEM",
    "build_language_agent_user_prompt",
    "CULTURAL_ADAPTATION_SYSTEM",
    "build_cultural_adaptation_user_prompt",
    "HUMOR_LOCALIZATION_SYSTEM",
    "build_humor_localization_user_prompt",
]
