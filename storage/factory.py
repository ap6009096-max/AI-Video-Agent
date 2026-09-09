"""Factory for object storage backends."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from core.logging import get_logger
from storage.base import ObjectStorage
from storage.local_storage import LocalObjectStorage

logger = get_logger(__name__)

# Set when Supabase was configured but health failed and we fell back to local.
_fallback_meta: dict[str, Any] = {"active": False, "reason": ""}


def _set_fallback(reason: str) -> None:
    _fallback_meta["active"] = True
    _fallback_meta["reason"] = reason or "Supabase unreachable"


def _clear_fallback() -> None:
    _fallback_meta["active"] = False
    _fallback_meta["reason"] = ""


@lru_cache
def get_object_storage() -> ObjectStorage:
    """Return Supabase storage when configured and healthy; else local mirror."""
    from config.settings import get_settings

    settings = get_settings()
    bucket = (settings.supabase_storage_bucket or "ai-video-agent").strip() or "ai-video-agent"

    if settings.has_supabase_storage:
        try:
            from storage.supabase_storage import SupabaseObjectStorage

            storage = SupabaseObjectStorage(
                url=settings.supabase_url,
                service_role_key=settings.supabase_service_role_key,
                bucket=bucket,
            )
            ok, detail = storage.health_check()
            if ok:
                _clear_fallback()
                logger.info("STORAGE_BACKEND=supabase bucket=%s", bucket)
                return storage
            reason = detail or "health_check failed"
            logger.warning(
                "STORAGE_BACKEND=supabase_fallback_local reason=%s",
                reason,
            )
            _set_fallback(reason)
        except Exception as exc:  # noqa: BLE001
            reason = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "STORAGE_BACKEND=supabase_fallback_local reason=%s",
                type(exc).__name__,
            )
            _set_fallback(reason)

    else:
        _clear_fallback()

    logger.info("STORAGE_BACKEND=local bucket=%s", bucket)
    return LocalObjectStorage(bucket=bucket)


def reset_object_storage_cache() -> None:
    """Clear cached storage instance (tests)."""
    get_object_storage.cache_clear()
    _clear_fallback()


def storage_health() -> tuple[str, bool, str]:
    """Return (backend_name, ok, detail) without exposing secrets."""
    storage = get_object_storage()
    if _fallback_meta.get("active"):
        return (
            "supabase_fallback_local",
            False,
            str(_fallback_meta.get("reason") or "Supabase unreachable; using local mirror"),
        )
    ok, detail = storage.health_check()
    return storage.backend_name, ok, detail


def storage_config_status() -> tuple[str, str]:
    """Return ``(status, detail)`` where status is missing|configured|unreachable.

    - missing: no service-role credentials
    - configured: Supabase selected and healthy
    - unreachable: credentials set but health failed (local fallback active)
    """
    from config.settings import get_settings

    settings = get_settings()
    if not settings.has_supabase_storage:
        url_ok = bool(settings.supabase_url.strip())
        key_ok = bool(settings.supabase_service_role_key.strip())
        bucket_ok = bool(settings.supabase_storage_bucket.strip())
        missing = []
        if not url_ok:
            missing.append("SUPABASE_URL")
        if not key_ok:
            missing.append("SUPABASE_SERVICE_ROLE_KEY")
        if not bucket_ok:
            missing.append("SUPABASE_STORAGE_BUCKET")
        return "missing", "Missing: " + (", ".join(missing) if missing else "credentials")
    # Force backend selection (may set fallback meta)
    _ = get_object_storage()
    if _fallback_meta.get("active"):
        return "unreachable", str(_fallback_meta.get("reason") or "health check failed")
    backend, ok, detail = storage_health()
    if backend == "supabase" and ok:
        return "configured", detail or "Connected"
    if not ok:
        return "unreachable", detail or "health check failed"
    return "configured", detail or "Connected"
