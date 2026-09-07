"""FFmpeg/ffprobe audio stream and volume/silence probing."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from core.logging import get_logger
from schemas.analysis import AudioCharacteristics, TimeRange
from tools.audio.ffmpeg_audio import resolve_ffmpeg_binary, resolve_ffprobe_binary

logger = get_logger(__name__)

_SILENCE_START = re.compile(r"silence_start:\s*([0-9.]+)")
_SILENCE_END = re.compile(r"silence_end:\s*([0-9.]+)")
_MEAN_VOLUME = re.compile(r"mean_volume:\s*([-0-9.]+)\s*dB")


def probe_audio_characteristics(media_path: str | Path) -> AudioCharacteristics:
    """Probe audio stream metadata and optional volume/silence stats."""
    path = Path(media_path)
    audio = AudioCharacteristics(has_audio=False)
    if not path.is_file():
        return audio

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
                    if stream.get("codec_type") == "audio":
                        audio.has_audio = True
                        try:
                            audio.sample_rate = int(stream.get("sample_rate") or 0) or None
                        except (TypeError, ValueError):
                            audio.sample_rate = None
                        try:
                            audio.channels = int(stream.get("channels") or 0) or None
                        except (TypeError, ValueError):
                            audio.channels = None
                        break
        except Exception as exc:  # noqa: BLE001
            logger.warning("ffprobe audio failed: %s", exc)

    ffmpeg = resolve_ffmpeg_binary()
    if ffmpeg and audio.has_audio:
        try:
            completed = subprocess.run(
                [
                    ffmpeg,
                    "-i",
                    str(path),
                    "-af",
                    "volumedetect,silencedetect=noise=-30dB:d=0.5",
                    "-f",
                    "null",
                    "-",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            stderr = completed.stderr or ""
            mean_match = _MEAN_VOLUME.search(stderr)
            if mean_match:
                audio.mean_volume_db = float(mean_match.group(1))
            starts = [float(m.group(1)) for m in _SILENCE_START.finditer(stderr)]
            ends = [float(m.group(1)) for m in _SILENCE_END.finditer(stderr)]
            ranges: list[TimeRange] = []
            for i, start in enumerate(starts):
                end = ends[i] if i < len(ends) else start
                if end >= start:
                    ranges.append(TimeRange(start=start, end=end))
            audio.silence_ranges = ranges
        except Exception as exc:  # noqa: BLE001
            logger.warning("ffmpeg audio filters failed: %s", exc)

    return audio
