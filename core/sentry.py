"""Optional Sentry error reporting (no-op when SENTRY_DSN is unset)."""

from __future__ import annotations

from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

_INITIALIZED = False


def init_sentry(
    dsn: str = "",
    *,
    app_env: str = "development",
    traces_sample_rate: float = 0.0,
) -> bool:
    """Initialize Sentry when a DSN is provided. Returns True if enabled."""
    global _INITIALIZED
    if _INITIALIZED:
        return True

    raw = (dsn or "").strip()
    if not raw:
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.logging import LoggingIntegration
    except ImportError:
        logger.warning(
            "SENTRY_DSN is set but sentry-sdk is not installed; error reporting disabled."
        )
        return False

    sentry_sdk.init(
        dsn=raw,
        environment=(app_env or "development").strip() or "development",
        traces_sample_rate=max(0.0, min(1.0, float(traces_sample_rate or 0.0))),
        integrations=[
            LoggingIntegration(level=None, event_level=None),
        ],
        send_default_pii=False,
    )
    _INITIALIZED = True
    logger.info("Sentry error reporting enabled (env=%s)", app_env)
    return True


def reset_sentry_for_tests() -> None:
    """Clear the init-once guard (tests only)."""
    global _INITIALIZED
    _INITIALIZED = False


def capture_exception(exc: BaseException, **kwargs: Any) -> None:
    """Forward an exception to Sentry when initialized; otherwise no-op."""
    if not _INITIALIZED:
        return
    try:
        import sentry_sdk

        sentry_sdk.capture_exception(exc, **kwargs)
    except Exception:  # noqa: BLE001
        logger.debug("Sentry capture_exception failed", exc_info=True)
