"""ThreadPool-backed async FFmpeg / render helpers (Rule 15)."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable, TypeVar

from core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

_EXECUTOR: ThreadPoolExecutor | None = None


def get_ffmpeg_executor(*, max_workers: int = 2) -> ThreadPoolExecutor:
    global _EXECUTOR
    if _EXECUTOR is None:
        _EXECUTOR = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="ffmpeg-pool"
        )
    return _EXECUTOR


def submit_ffmpeg(
    fn: Callable[..., T],
    *args: Any,
    **kwargs: Any,
) -> Future[T]:
    """Submit a blocking FFmpeg/render callable to the shared pool."""
    ex = get_ffmpeg_executor()
    logger.debug("ffmpeg pool submit %s", getattr(fn, "__name__", fn))
    return ex.submit(fn, *args, **kwargs)


def run_in_ffmpeg_pool(
    fn: Callable[..., T],
    *args: Any,
    timeout: float | None = None,
    **kwargs: Any,
) -> T:
    """Submit and wait (UI can instead hold the Future and poll)."""
    fut = submit_ffmpeg(fn, *args, **kwargs)
    return fut.result(timeout=timeout)


def shutdown_ffmpeg_executor(wait: bool = False) -> None:
    global _EXECUTOR
    if _EXECUTOR is not None:
        _EXECUTOR.shutdown(wait=wait, cancel_futures=False)
        _EXECUTOR = None
