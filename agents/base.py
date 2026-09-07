"""Base agent interface for future Gemini-backed agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    """Abstract agent stub — concrete agents land in later prompts."""

    name: str = "base"

    @abstractmethod
    def run(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the agent and return a result."""
        raise NotImplementedError


class PlaceholderAgent(BaseAgent):
    """No-op agent used by the foundation workflow smoke test."""

    name = "placeholder"

    def run(self, user_input: str = "", **_: Any) -> dict[str, str]:
        """Echo input without calling any LLM."""
        return {
            "agent": self.name,
            "echo": user_input,
            "detail": "Placeholder agent — Gemini integration arrives in later prompts.",
        }
