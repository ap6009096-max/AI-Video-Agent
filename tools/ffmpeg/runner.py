"""Shared FFmpeg subprocess runner."""

from __future__ import annotations

import subprocess
from pathlib import Path

from core.logging import get_logger
from tools.ffmpeg.bin import resolve_ffmpeg_binary

logger = get_logger(__name__)


def run_ffmpeg(args: list[str], *, timeout: int = 900) -> bool:
    """Run ffmpeg with args (without binary). Returns True on success."""
    ffmpeg = resolve_ffmpeg_binary()
    if not ffmpeg:
        logger.info("FFmpeg not found")
        return False
    cmd = [ffmpeg, "-y", *args]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, check=False, timeout=timeout
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("FFmpeg failed: %s", exc)
        return False
    if proc.returncode != 0:
        logger.warning("FFmpeg code=%s stderr=%s", proc.returncode, (proc.stderr or "")[:400])
        return False
    return True


def ok_output(path: Path) -> Path | None:
    if path.is_file() and path.stat().st_size > 0:
        return path.resolve()
    if path.exists() and path.stat().st_size <= 0:
        try:
            path.unlink()
        except OSError:
            pass
    return None
