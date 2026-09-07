"""OpenCV / ffprobe video property probing."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from core.errors import VideoUnderstandingError
from core.logging import get_logger
from schemas.analysis import VideoProperties
from tools.audio.ffmpeg_audio import resolve_ffprobe_binary

logger = get_logger(__name__)

# Re-export for tools.video.__init__ and callers
__all__ = ["compute_frame_step", "probe_video_properties", "resolve_ffprobe_binary"]


def probe_video_properties(media_path: str | Path) -> VideoProperties:
    """Probe duration/FPS/resolution via OpenCV, with optional ffprobe codecs."""
    path = Path(media_path)
    if not path.is_file():
        raise VideoUnderstandingError(f"Media file not found: {path}")

    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise VideoUnderstandingError(
            "opencv-python-headless is not installed. Run: pip install opencv-python-headless"
        ) from exc

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise VideoUnderstandingError(f"OpenCV could not open video: {path}")

    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        duration = (frame_count / fps) if fps > 0 else 0.0
    finally:
        cap.release()

    video_codec = ""
    audio_codec = ""
    ffprobe = resolve_ffprobe_binary()
    if ffprobe:
        try:
            completed = subprocess.run(
                [
                    ffprobe,
                    "-v",
                    "quiet",
                    "-print_format",
                    "json",
                    "-show_streams",
                    str(path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            if completed.returncode == 0 and completed.stdout:
                payload = json.loads(completed.stdout)
                for stream in payload.get("streams") or []:
                    codec = str(stream.get("codec_name") or "")
                    if stream.get("codec_type") == "video" and not video_codec:
                        video_codec = codec
                        # Prefer ffprobe duration when available
                        dur = stream.get("duration")
                        if dur is not None:
                            try:
                                duration = max(duration, float(dur))
                            except ValueError:
                                pass
                    if stream.get("codec_type") == "audio" and not audio_codec:
                        audio_codec = codec
        except Exception as exc:  # noqa: BLE001
            logger.warning("ffprobe enrichment failed: %s", exc)

    return VideoProperties(
        duration_seconds=float(duration),
        fps=float(fps),
        width=width,
        height=height,
        frame_count=frame_count,
        video_codec=video_codec,
        audio_codec=audio_codec,
    )


def compute_frame_step(
    video_fps: float,
    sample_fps: float,
    frame_count: int,
    max_frames: int,
) -> int:
    """Compute stride between analyzed frames (never analyze every frame by default)."""
    vf = video_fps if video_fps > 0 else 30.0
    sf = sample_fps if sample_fps > 0 else 1.0
    step = max(1, int(round(vf / sf)))
    projected = max(1, frame_count // step) if frame_count > 0 else max_frames
    if projected > max_frames and frame_count > 0:
        step = max(step, int(round(frame_count / max_frames)))
    return max(1, step)
