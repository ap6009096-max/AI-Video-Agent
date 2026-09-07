"""Cut and join media segments."""

from __future__ import annotations

import tempfile
from pathlib import Path

from core.logging import get_logger
from tools.ffmpeg.runner import ok_output, run_ffmpeg

logger = get_logger(__name__)


def cut_segment(
    media_path: str | Path,
    output_path: str | Path,
    *,
    start: float,
    end: float,
) -> Path | None:
    """Cut [start, end) from media. Soft-skip if FFmpeg unavailable."""
    media = Path(media_path)
    out = Path(output_path)
    if not media.is_file() or end <= start:
        return None
    out.parent.mkdir(parents=True, exist_ok=True)
    dur = max(0.05, end - start)
    ok = run_ffmpeg(
        [
            "-ss",
            f"{start:.3f}",
            "-i",
            str(media.resolve()),
            "-t",
            f"{dur:.3f}",
            "-c",
            "copy",
            str(out.resolve()),
        ]
    )
    if not ok:
        # Re-encode fallback when copy fails
        ok = run_ffmpeg(
            [
                "-ss",
                f"{start:.3f}",
                "-i",
                str(media.resolve()),
                "-t",
                f"{dur:.3f}",
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                str(out.resolve()),
            ]
        )
    return ok_output(out) if ok else None


def concat_segments(
    segment_paths: list[str | Path],
    output_path: str | Path,
) -> Path | None:
    """Join segments via concat demuxer."""
    paths = [Path(p) for p in segment_paths if Path(p).is_file()]
    if not paths:
        return None
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if len(paths) == 1:
        # Single file — remux/copy
        ok = run_ffmpeg(["-i", str(paths[0].resolve()), "-c", "copy", str(out.resolve())])
        return ok_output(out) if ok else None

    with tempfile.TemporaryDirectory(prefix="concat_") as tmp:
        list_file = Path(tmp) / "list.txt"
        lines = []
        for p in paths:
            escaped = str(p.resolve()).replace("\\", "/").replace("'", "'\\''")
            lines.append(f"file '{escaped}'")
        list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        ok = run_ffmpeg(
            [
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_file.resolve()),
                "-c",
                "copy",
                str(out.resolve()),
            ]
        )
        if not ok:
            ok = run_ffmpeg(
                [
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(list_file.resolve()),
                    "-c:v",
                    "libx264",
                    "-c:a",
                    "aac",
                    str(out.resolve()),
                ]
            )
        return ok_output(out) if ok else None
