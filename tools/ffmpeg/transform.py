"""Resize / reframe transform helpers."""

from __future__ import annotations

from pathlib import Path

from tools.ffmpeg.runner import ok_output, run_ffmpeg


def resize(
    media_path: str | Path,
    output_path: str | Path,
    *,
    width: int,
    height: int,
) -> Path | None:
    """Scale and pad to exact width x height."""
    media = Path(media_path)
    out = Path(output_path)
    if not media.is_file() or width < 2 or height < 2:
        return None
    out.parent.mkdir(parents=True, exist_ok=True)
    w = width - (width % 2)
    h = height - (height % 2)
    vf = (
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2"
    )
    ok = run_ffmpeg(
        [
            "-i",
            str(media.resolve()),
            "-vf",
            vf,
            "-c:a",
            "copy",
            str(out.resolve()),
        ]
    )
    return ok_output(out) if ok else None


def reframe_crop_scale(
    media_path: str | Path,
    output_path: str | Path,
    *,
    crop_w: int,
    crop_h: int,
    crop_x: int,
    crop_y: int,
    out_w: int,
    out_h: int,
) -> Path | None:
    """Crop then scale to output size."""
    media = Path(media_path)
    out = Path(output_path)
    if not media.is_file():
        return None
    out.parent.mkdir(parents=True, exist_ok=True)
    vf = f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y},scale={out_w}:{out_h}"
    ok = run_ffmpeg(
        [
            "-i",
            str(media.resolve()),
            "-vf",
            vf,
            "-c:a",
            "aac",
            str(out.resolve()),
        ]
    )
    return ok_output(out) if ok else None
