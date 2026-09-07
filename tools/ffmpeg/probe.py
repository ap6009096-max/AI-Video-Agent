"""Unified media probing via ffprobe / OpenCV fallback."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from core.logging import get_logger
from tools.ffmpeg.bin import resolve_ffprobe_binary

logger = get_logger(__name__)


def probe_media(media_path: str | Path) -> dict[str, Any] | None:
    """Return unified probe dict or None if unreadable."""
    path = Path(media_path)
    if not path.is_file():
        return None

    ffprobe = resolve_ffprobe_binary()
    result: dict[str, Any] = {
        "path": str(path.resolve()),
        "exists": True,
        "duration": 0.0,
        "width": 0,
        "height": 0,
        "fps": 0.0,
        "video_codec": "",
        "audio_codec": "",
        "audio_sample_rate": 0,
        "has_audio": False,
        "has_video": False,
        "container": path.suffix.lstrip(".").lower(),
    }

    if ffprobe:
        try:
            proc = subprocess.run(
                [
                    ffprobe,
                    "-v",
                    "quiet",
                    "-print_format",
                    "json",
                    "-show_format",
                    "-show_streams",
                    str(path),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
            )
            if proc.returncode == 0 and proc.stdout:
                payload = json.loads(proc.stdout)
                fmt = payload.get("format") or {}
                try:
                    result["duration"] = float(fmt.get("duration") or 0.0)
                except (TypeError, ValueError):
                    pass
                for stream in payload.get("streams") or []:
                    if stream.get("codec_type") == "video" and not result["has_video"]:
                        result["has_video"] = True
                        result["video_codec"] = str(stream.get("codec_name") or "")
                        try:
                            result["width"] = int(stream.get("width") or 0)
                            result["height"] = int(stream.get("height") or 0)
                        except (TypeError, ValueError):
                            pass
                        # fps from avg_frame_rate
                        afr = str(stream.get("avg_frame_rate") or "0/1")
                        if "/" in afr:
                            num, den = afr.split("/", 1)
                            try:
                                den_f = float(den) or 1.0
                                result["fps"] = float(num) / den_f
                            except (TypeError, ValueError):
                                pass
                    if stream.get("codec_type") == "audio" and not result["has_audio"]:
                        result["has_audio"] = True
                        result["audio_codec"] = str(stream.get("codec_name") or "")
                        try:
                            result["audio_sample_rate"] = int(
                                float(stream.get("sample_rate") or 0)
                            )
                        except (TypeError, ValueError):
                            pass
                return result
        except Exception as exc:  # noqa: BLE001
            logger.warning("ffprobe failed: %s", exc)

    # OpenCV fallback for video props
    try:
        import cv2  # type: ignore

        cap = cv2.VideoCapture(str(path))
        if cap.isOpened():
            result["has_video"] = True
            result["fps"] = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
            result["width"] = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            result["height"] = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            if result["fps"] > 0 and frames > 0:
                result["duration"] = frames / result["fps"]
            cap.release()
            return result
    except Exception as exc:  # noqa: BLE001
        logger.warning("OpenCV probe failed: %s", exc)

    return (
        result
        if (
            result["duration"]
            or result["width"]
            or result["has_video"]
            or result["has_audio"]
            or (path.is_file() and path.stat().st_size > 0)
        )
        else None
    )

