"""Burn captions into video via FFmpeg (soft-skip when unavailable)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from core.logging import get_logger
from tools.audio.ffmpeg_audio import resolve_ffmpeg_binary

logger = get_logger(__name__)


def burn_captions(
    media_path: str | Path,
    subtitle_path: str | Path,
    output_path: str | Path,
) -> Path | None:
    """Burn ASS/SRT into video with FFmpeg. Returns output path or None.

    Soft-skips (returns None) when FFmpeg is missing, media is missing,
    or the burn-in process fails — never invents an output file.
    """
    ffmpeg = resolve_ffmpeg_binary()
    if not ffmpeg:
        logger.info("FFmpeg not found — skipping caption burn-in")
        return None

    media = Path(media_path)
    subs = Path(subtitle_path)
    out = Path(output_path)
    if not media.is_file():
        logger.info("Media missing for burn-in: %s", media)
        return None
    if not subs.is_file():
        logger.info("Subtitle file missing for burn-in: %s", subs)
        return None

    out.parent.mkdir(parents=True, exist_ok=True)
    # Escape path for subtitles filter (Windows-friendly)
    sub_escaped = str(subs.resolve()).replace("\\", "/").replace(":", "\\:")
    vf = f"subtitles='{sub_escaped}'"
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(media.resolve()),
        "-vf",
        vf,
        "-c:a",
        "copy",
        str(out.resolve()),
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=600,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("Caption burn-in failed: %s", exc)
        return None

    if proc.returncode != 0 or not out.is_file() or out.stat().st_size <= 0:
        logger.warning(
            "Caption burn-in unsuccessful code=%s stderr=%s",
            proc.returncode,
            (proc.stderr or "")[:500],
        )
        if out.exists() and out.stat().st_size <= 0:
            try:
                out.unlink()
            except OSError:
                pass
        return None

    logger.info("Burned-in captions written to %s", out)
    return out.resolve()
