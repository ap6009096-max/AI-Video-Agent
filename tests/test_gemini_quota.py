"""Regression tests for bounded Gemini quota handling."""

from __future__ import annotations

import pytest

from core.errors import (
    GeminiAuthenticationError,
    GeminiGenerationError,
    GeminiModelUnavailableError,
    GeminiQuotaExhaustedError,
)
from schemas.story import GeminiClipStory, GeminiStoriesBatch
from tools.llm import gemini


class _FakeStructured:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = outcomes
        self.calls = 0

    def with_structured_output(self, _schema):
        return self

    def invoke(self, _messages):
        outcome = self.outcomes[min(self.calls, len(self.outcomes) - 1)]
        self.calls += 1
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def _success() -> GeminiStoriesBatch:
    return GeminiStoriesBatch(
        stories=[
            GeminiClipStory(
                clip_id=0,
                hook="Hook",
                context="Context",
                value_event="Value",
                payoff="Payoff",
                cta="CTA",
            )
        ]
    )


def _configure(monkeypatch: pytest.MonkeyPatch, *, fallback: str = "", retries: str = "2") -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "primary-model")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", fallback)
    monkeypatch.setenv("GEMINI_MAX_RETRIES", retries)
    monkeypatch.setenv("GEMINI_RETRY_BASE_SECONDS", "0")
    monkeypatch.setenv("GEMINI_RETRY_MAX_SECONDS", "0")
    gemini.get_settings.cache_clear()
    monkeypatch.setattr(gemini.time, "sleep", lambda _seconds: None)


def test_daily_quota_does_not_retry_primary(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch, retries="2")
    model = _FakeStructured(
        [RuntimeError("429 RESOURCE_EXHAUSTED GenerateRequestsPerDayPerModel-FreeTier")]
    )

    with pytest.raises(GeminiQuotaExhaustedError):
        gemini.generate_clip_stories(["clip"], model=model)

    assert model.calls == 1


def test_temporary_429_retries_with_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch, retries="2")
    model = _FakeStructured([RuntimeError("429 temporary rate limit"), _success()])

    result = gemini.generate_clip_stories(["clip"], model=model)

    assert result.stories[0].hook == "Hook"
    assert model.calls == 2


def test_server_error_retries_with_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch, retries="2")
    model = _FakeStructured([RuntimeError("503 service unavailable"), _success()])

    gemini.generate_clip_stories(["clip"], model=model)

    assert model.calls == 2


def test_authentication_error_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch, retries="2")
    model = _FakeStructured([RuntimeError("401 API key invalid")])

    with pytest.raises(GeminiAuthenticationError):
        gemini.generate_clip_stories(["clip"], model=model)

    assert model.calls == 1


def test_invalid_primary_uses_configured_fallback_once(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch, fallback="fallback-model", retries="2")
    primary = _FakeStructured([RuntimeError("404 model not found")])
    fallback = _FakeStructured([_success()])
    models = {"fallback-model": fallback}

    def fake_get_chat_model(*, model_name=None, **_kwargs):
        assert model_name == "fallback-model"
        return models[model_name]

    monkeypatch.setattr(gemini, "get_chat_model", fake_get_chat_model)
    result = gemini.generate_clip_stories(["clip"], model=primary)

    assert result.stories[0].hook == "Hook"
    assert primary.calls == 1
    assert fallback.calls == 1


def test_daily_quota_skips_primary_retries_and_uses_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch, fallback="fallback-model", retries="2")
    primary = _FakeStructured(
        [RuntimeError("429 RESOURCE_EXHAUSTED GenerateRequestsPerDayPerModel-FreeTier")]
    )
    fallback = _FakeStructured([_success()])
    monkeypatch.setattr(
        gemini,
        "get_chat_model",
        lambda *, model_name=None, **_kwargs: fallback,
    )

    result = gemini.generate_clip_stories(["clip"], model=primary)

    assert result.stories[0].hook == "Hook"
    assert primary.calls == 1
    assert fallback.calls == 1


def test_all_daily_exhausted_models_stop_without_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch, fallback="fallback-model", retries="2")
    primary = _FakeStructured([RuntimeError("429 quota exceeded GenerateRequestsPerDayPerModel-FreeTier")])
    fallback = _FakeStructured([RuntimeError("429 quota exceeded GenerateRequestsPerDayPerModel-FreeTier")])

    monkeypatch.setattr(
        gemini,
        "get_chat_model",
        lambda *, model_name=None, **_kwargs: fallback,
    )
    with pytest.raises(GeminiQuotaExhaustedError):
        gemini.generate_clip_stories(["clip"], model=primary)

    assert primary.calls == 1
    assert fallback.calls == 1


def test_unexpected_error_is_not_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch, retries="2")
    model = _FakeStructured([ValueError("programming failure")])

    with pytest.raises(GeminiGenerationError, match="programming failure"):
        gemini.generate_clip_stories(["clip"], model=model)

    assert model.calls == 1
