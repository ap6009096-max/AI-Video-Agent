"""FFmpeg encoding for smart reframe crop windows."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from core.logging import get_logger
from schemas.reframe import ReframePlan
from tools.audio.ffmpeg_audio import resolve_ffmpeg_binary

logger = get_logger(__name__)


def render_reframe(
    media_path: str | Path,
    plan: ReframePlan,
    output_path: str | Path,
) -> Path | None:
    """Encode reframed video from plan windows. Returns path or None (soft-skip)."""
    ffmpeg = resolve_ffmpeg_binary()
    if not ffmpeg:
        logger.info("FFmpeg not found — skipping reframe encode")
        return None

    media = Path(media_path)
    out = Path(output_path)
    if not media.is_file():
        logger.info("Media missing for reframe: %s", media)
        return None
    if plan.skipped or not plan.clip_plans:
        return None

    out.parent.mkdir(parents=True, exist_ok=True)
    ow = max(2, plan.output_width - (plan.output_width % 2))
    oh = max(2, plan.output_height - (plan.output_height % 2))

    # Collect all crop windows across clips
    windows = []
    for clip in plan.clip_plans:
        windows.extend(clip.windows)
    if not windows:
        return None

    # Passthrough / single window → one ffmpeg call
    if plan.passthrough or len(windows) == 1:
        w = windows[0]
        vf = (
            f"crop={w.crop_w}:{w.crop_h}:{w.crop_x}:{w.crop_y},"
            f"scale={ow}:{oh}"
        )
        if plan.passthrough:
            vf = f"scale={ow}:{oh}:force_original_aspect_ratio=decrease,"
            vf += f"pad={ow}:{oh}:(ow-iw)/2:(oh-ih)/2"
        ss = w.start
        dur = max(0.05, w.end - w.start)
        cmd = [
            ffmpeg,
            "-y",
            "-ss",
            f"{ss:.3f}",
            "-i",
            str(media.resolve()),
            "-t",
            f"{dur:.3f}",
            "-vf",
            vf,
            "-c:a",
            "aac",
            "-shortest",
            str(out.resolve()),
        ]
        return _run(cmd, out)

    # Multi-window: encode segments then concat
    with tempfile.TemporaryDirectory(prefix="reframe_") as tmp:
        tmp_path = Path(tmp)
        parts: list[Path] = []
        list_file = tmp_path / "concat.txt"
        lines: list[str] = []
        for i, w in enumerate(windows):
            part = tmp_path / f"part_{i:04d}.mp4"
            vf = (
                f"crop={w.crop_w}:{w.crop_h}:{w.crop_x}:{w.crop_y},"
                f"scale={ow}:{oh}"
            )
            dur = max(0.05, w.end - w.start)
            cmd = [
                ffmpeg,
                "-y",
                "-ss",
                f"{w.start:.3f}",
                "-i",
                str(media.resolve()),
                "-t",
                f"{dur:.3f}",
                "-vf",
                vf,
                "-an",
                str(part.resolve()),
            ]
            if _run(cmd, part) is None:
                logger.warning("Reframe segment %s failed", i)
                continue
            parts.append(part)
            # concat demuxer needs escaped paths
            p = str(part.resolve()).replace("\\", "/")
            lines.append(f"file '{p}'")
        if not parts:
            return None
        list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        cmd = [
            ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file.resolve()),
            "-i",
            str(media.resolve()),
            "-map",
            "0:v",
            "-map",
            "1:a?",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-shortest",
            str(out.resolve()),
        ]
        return _run(cmd, out)


def _run(cmd: list[str], out: Path) -> Path | None:
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=900,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("Reframe FFmpeg failed: %s", exc)
        return None
    if proc.returncode != 0 or not out.is_file() or out.stat().st_size <= 0:
        logger.warning(
            "Reframe encode unsuccessful code=%s stderr=%s",
            proc.returncode,
            (proc.stderr or "")[:400],
        )
        if out.exists() and out.stat().st_size <= 0:
            try:
                out.unlink()
            except OSError:
                pass
        return None
    logger.info("Reframed video written to %s", out)
    return out.resolve()
