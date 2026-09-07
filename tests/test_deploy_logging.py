"""Tests for logging and optional Sentry wiring."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.logging import configure_logging, get_logger, reset_logging_for_tests
from core.sentry import init_sentry, reset_sentry_for_tests


@pytest.fixture(autouse=True)
def _reset_logging_and_sentry() -> None:
    reset_logging_for_tests()
    reset_sentry_for_tests()
    yield
    reset_logging_for_tests()
    reset_sentry_for_tests()


def test_configure_logging_idempotent_and_level() -> None:
    configure_logging("WARNING", app_env="development")
    root = logging.getLogger()
    assert root.level == logging.WARNING
    assert len(root.handlers) >= 1

    first_handlers = list(root.handlers)
    configure_logging("DEBUG", app_env="development")
    assert list(root.handlers) == first_handlers
    assert root.level == logging.WARNING  # second call is a no-op


def test_production_format_includes_env() -> None:
    configure_logging("INFO", app_env="production")
    handler = logging.getLogger().handlers[0]
    fmt = handler.formatter._fmt if handler.formatter else ""
    assert "app_env" in fmt


def test_log_to_file_writes_rotating_log(tmp_path: Path) -> None:
    configure_logging(
        "INFO",
        app_env="production",
        log_to_file=True,
        output_dir=tmp_path,
    )
    log = get_logger("test.deploy")
    log.info("hello deploy")
    path = tmp_path / "logs" / "app.log"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "hello deploy" in text
    assert "env=production" in text


def test_sentry_noop_when_dsn_empty() -> None:
    assert init_sentry("") is False
    assert init_sentry("   ") is False


def test_sentry_init_when_dsn_set(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_sdk = MagicMock()
    fake_integrations = MagicMock()
    monkeypatch.setitem(
        __import__("sys").modules,
        "sentry_sdk",
        fake_sdk,
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "sentry_sdk.integrations.logging",
        fake_integrations,
    )
    fake_integrations.LoggingIntegration = MagicMock(return_value=MagicMock())

    enabled = init_sentry(
        "https://examplePublicKey@o0.ingest.sentry.io/0",
        app_env="production",
        traces_sample_rate=0.0,
    )
    assert enabled is True
    fake_sdk.init.assert_called_once()
    kwargs = fake_sdk.init.call_args.kwargs
    assert kwargs["dsn"].startswith("https://")
    assert kwargs["environment"] == "production"
    assert kwargs["traces_sample_rate"] == 0.0
