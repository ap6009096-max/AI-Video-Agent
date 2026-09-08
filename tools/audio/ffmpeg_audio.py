"""Optional FFmpeg audio extraction for Whisper ASR."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import imageio_ffmpeg

from config.settings import get_settings
from core.errors import TranscriptAgentError
from core.logging import get_logger

logger = get_logger(__name__)


def resolve_ffmpeg_binary() -> str | None:
    """Return the configured or bundled FFmpeg executable path."""
    configured = get_settings().ffmpeg_path.strip()
    if configured:
        path = Path(configured)
        if path.is_file():
            return str(path.resolve())
    try:
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        logger.warning("imageio-ffmpeg executable is unavailable")
        return None


def resolve_ffprobe_binary() -> str | None:
    """Return ffprobe next to ffmpeg or on PATH."""
    ffmpeg = resolve_ffmpeg_binary()
    if ffmpeg:
        sibling = Path(ffmpeg).with_name("ffprobe")
        suffixed = sibling.with_suffix(Path(ffmpeg).suffix)
        if sibling.is_file():
            return str(sibling)
        if suffixed.is_file():
            return str(suffixed)
        found = shutil.which("ffprobe")
        if found:
            return found
    return shutil.which("ffprobe")


def extract_wav_for_asr(media_path: str | Path, output_wav: str | Path) -> Path | None:
    """Extract mono 16 kHz WAV for ASR when FFmpeg is available.

    Returns the WAV path on success, or None if FFmpeg is unavailable
    (caller should pass the original media path to Whisper).
    """
    ffmpeg = resolve_ffmpeg_binary()
    if not ffmpeg:
        logger.info("FFmpeg not found — Whisper will read media directly")
        return None

    media = Path(media_path)
    out = Path(output_wav)
    out.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(media),
        "-ac",
        "1",
        "-ar",
        "16000",
        "-vn",
        str(out),
    ]
    try:
        completed = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        logger.warning("FFmpeg invoke failed: %s", exc)
        return None

    if completed.returncode != 0 or not out.is_file():
        logger.warning(
            "FFmpeg audio extract failed (code=%s): %s",
            completed.returncode,
            (completed.stderr or "")[:400],
        )
        return None

    logger.info("Extracted ASR audio to %s", out)
    return out.resolve()


def require_media_file(media_path: str | Path) -> Path:
    """Validate that a media file exists."""
    path = Path(media_path)
    if not path.is_file():
        raise TranscriptAgentError(f"Media file not found: {path}")
    return path.resolve()
