"""Strict playable-media validation (no invented probe fields)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from tools.ffmpeg.probe import probe_media


@dataclass(slots=True)
class ValidationResult:
    """Outcome of ``validate_video``."""

    ok: bool
    path: str = ""
    reason: str = ""
    duration: float = 0.0
    width: int = 0
    height: int = 0
    fps: float = 0.0
    has_video: bool = False
    has_audio: bool = False
    size_bytes: int = 0
    checks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_video(
    path: str | Path | None,
    *,
    require_audio: bool = False,
    min_duration: float = 0.05,
    max_av_delta: float = 0.5,
    min_width: int = 2,
    min_height: int = 2,
) -> ValidationResult:
    """Return whether ``path`` is a real playable video (fail closed)."""
    if not path:
        return ValidationResult(ok=False, reason="No media path provided")
    media = Path(path)
    result = ValidationResult(ok=False, path=str(media))
    if not media.is_file():
        result.reason = "File does not exist"
        return result
    size = int(media.stat().st_size)
    result.size_bytes = size
    if size <= 0:
        result.reason = "File is empty"
        return result
    result.checks.append("file_exists")
    result.checks.append("file_size")

    info = probe_media(media)
    if not info:
        result.reason = "Could not probe media — file may be corrupt or not a video"
        return result

    # Reject stubs that only reflect "file exists" without streams
    has_video = bool(info.get("has_video"))
    has_audio = bool(info.get("has_audio"))
    duration = float(info.get("duration") or 0.0)
    width = int(info.get("width") or 0)
    height = int(info.get("height") or 0)
    fps = float(info.get("fps") or 0.0)

    result.has_video = has_video
    result.has_audio = has_audio
    result.duration = duration
    result.width = width
    result.height = height
    result.fps = fps

    if not has_video:
        result.reason = "No video stream found"
        return result
    result.checks.append("video_stream")

    if duration < min_duration:
        result.reason = f"Invalid duration ({duration:.3f}s)"
        return result
    result.checks.append("duration")

    if width < min_width or height < min_height:
        result.reason = f"Invalid resolution ({width}x{height})"
        return result
    result.checks.append("resolution")

    if fps <= 0:
        result.reason = f"Invalid frame rate ({fps})"
        return result
    result.checks.append("fps")

    if require_audio and not has_audio:
        result.reason = "Audio stream required but missing"
        return result
    if has_audio:
        result.checks.append("audio_stream")
        # Optional A/V sync check when both durations are available
        audio_dur = float(info.get("audio_duration") or 0.0)
        if audio_dur > 0 and abs(audio_dur - duration) > max_av_delta:
            result.reason = (
                f"Audio/video duration mismatch "
                f"(video={duration:.2f}s audio={audio_dur:.2f}s)"
            )
            return result

    result.ok = True
    result.reason = "ok"
    return result


def is_valid_video(path: str | Path | None, **kwargs: Any) -> bool:
    return validate_video(path, **kwargs).ok
