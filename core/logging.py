"""Logging setup for the AI Video Agent."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_CONFIGURED = False


class _NamePrefixFilter(logging.Filter):
    """Allow records whose logger name starts with any of the prefixes."""

    def __init__(self, prefixes: tuple[str, ...]) -> None:
        super().__init__()
        self.prefixes = prefixes

    def filter(self, record: logging.LogRecord) -> bool:
        name = record.name or ""
        return any(name.startswith(p) for p in self.prefixes)


class _ExcludePrefixFilter(logging.Filter):
    """Drop records matching prefixes (used to keep app.log general)."""

    def __init__(self, prefixes: tuple[str, ...]) -> None:
        super().__init__()
        self.prefixes = prefixes

    def filter(self, record: logging.LogRecord) -> bool:
        name = record.name or ""
        return not any(name.startswith(p) for p in self.prefixes)


def reset_logging_for_tests() -> None:
    """Clear the configure-once guard (tests only)."""
    global _CONFIGURED
    _CONFIGURED = False
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()


def configure_logging(
    level: str = "INFO",
    *,
    app_env: str = "development",
    log_to_file: bool = False,
    output_dir: str | Path = "outputs",
) -> None:
    """Configure root logging once with a structured format.

    Stdout is always enabled (Docker/journald friendly). When ``log_to_file``
    is true, also write a rotating log under ``{output_dir}/logs/app.log``.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_level = getattr(logging, level.upper(), logging.INFO)
    env_label = (app_env or "development").strip() or "development"
    production = env_label.lower() in {"production", "prod"}

    if production:
        fmt = (
            "%(asctime)s | %(levelname)s | env=%(app_env)s | "
            "%(name)s | %(message)s"
        )
    else:
        fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    formatter = logging.Formatter(fmt=fmt, datefmt="%Y-%m-%d %H:%M:%S")

    class _EnvFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            if not hasattr(record, "app_env"):
                record.app_env = env_label  # type: ignore[attr-defined]
            return True

    env_filter = _EnvFilter()

    stdout = logging.StreamHandler(sys.stdout)
    stdout.setFormatter(formatter)
    stdout.addFilter(env_filter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(stdout)
    root.setLevel(log_level)

    if log_to_file:
        log_dir = Path(output_dir) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        for log_name in ("app.log", "render.log", "graph.log"):
            file_handler = RotatingFileHandler(
                log_dir / log_name,
                maxBytes=5_000_000,
                backupCount=3,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            file_handler.addFilter(env_filter)
            if log_name == "render.log":
                file_handler.addFilter(_NamePrefixFilter(("tools.ffmpeg", "tools.reframe", "agents.render")))
            elif log_name == "graph.log":
                file_handler.addFilter(_NamePrefixFilter(("graph.", "agents.")))
            else:
                file_handler.addFilter(_ExcludePrefixFilter(("tools.ffmpeg",)))
            root.addHandler(file_handler)

    # Keep noisy third-party loggers quieter by default
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a named logger."""
    return logging.getLogger(name)
