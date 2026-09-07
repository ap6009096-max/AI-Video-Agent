"""Encoding and format conversion."""

from __future__ import annotations

from pathlib import Path

from tools.ffmpeg.runner import ok_output, run_ffmpeg


def encode_mp4(
    media_path: str | Path,
    output_path: str | Path,
    *,
    fps: float | None = None,
    width: int | None = None,
    height: int | None = None,
) -> Path | None:
    """Re-encode to H.264/AAC MP4 with optional fps/scale."""
    media = Path(media_path)
    out = Path(output_path)
    if not media.is_file():
        return None
    out.parent.mkdir(parents=True, exist_ok=True)
    args: list[str] = ["-i", str(media.resolve())]
    vf_parts: list[str] = []
    if width and height:
        w = width - (width % 2)
        h = height - (height % 2)
        vf_parts.append(
            f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2"
        )
    if fps and fps > 0:
        vf_parts.append(f"fps={fps}")
    if vf_parts:
        args.extend(["-vf", ",".join(vf_parts)])
    args.extend(["-c:v", "libx264", "-c:a", "aac", "-movflags", "+faststart", str(out.resolve())])
    ok = run_ffmpeg(args)
    return ok_output(out) if ok else None


def convert_format(
    media_path: str | Path,
    output_path: str | Path,
) -> Path | None:
    """Convert container/codec to destination extension."""
    media = Path(media_path)
    out = Path(output_path)
    if not media.is_file():
        return None
    out.parent.mkdir(parents=True, exist_ok=True)
    ok = run_ffmpeg(
        [
            "-i",
            str(media.resolve()),
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            str(out.resolve()),
        ]
    )
    return ok_output(out) if ok else None
