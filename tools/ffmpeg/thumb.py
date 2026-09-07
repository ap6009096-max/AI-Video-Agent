"""Thumbnail extraction."""

from __future__ import annotations

from pathlib import Path

from tools.ffmpeg.runner import ok_output, run_ffmpeg


def extract_thumbnail(
    media_path: str | Path,
    output_path: str | Path,
    *,
    time_seconds: float = 1.0,
) -> Path | None:
    media = Path(media_path)
    out = Path(output_path)
    if not media.is_file():
        return None
    out.parent.mkdir(parents=True, exist_ok=True)
    ok = run_ffmpeg(
        [
            "-ss",
            f"{max(0.0, time_seconds):.3f}",
            "-i",
            str(media.resolve()),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(out.resolve()),
        ]
    )
    return ok_output(out) if ok else None
