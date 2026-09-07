"""Subtitle burn-in and soft mux."""

from __future__ import annotations

from pathlib import Path

from tools.captions.burnin import burn_captions
from tools.ffmpeg.runner import ok_output, run_ffmpeg


def burn_subtitles(
    media_path: str | Path,
    subtitle_path: str | Path,
    output_path: str | Path,
) -> Path | None:
    """Burn ASS/SRT into video (wraps captions burnin)."""
    return burn_captions(media_path, subtitle_path, output_path)


def mux_soft_subs(
    media_path: str | Path,
    subtitle_path: str | Path,
    output_path: str | Path,
) -> Path | None:
    """Mux soft subtitles as a separate stream."""
    media = Path(media_path)
    subs = Path(subtitle_path)
    out = Path(output_path)
    if not media.is_file() or not subs.is_file():
        return None
    out.parent.mkdir(parents=True, exist_ok=True)
    ok = run_ffmpeg(
        [
            "-i",
            str(media.resolve()),
            "-i",
            str(subs.resolve()),
            "-c",
            "copy",
            "-c:s",
            "mov_text",
            str(out.resolve()),
        ]
    )
    return ok_output(out) if ok else None
