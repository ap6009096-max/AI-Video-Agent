"""FFmpeg / ffprobe binary resolution (wraps existing audio helpers)."""

from __future__ import annotations

from tools.audio.ffmpeg_audio import resolve_ffmpeg_binary, resolve_ffprobe_binary

__all__ = ["resolve_ffmpeg_binary", "resolve_ffprobe_binary"]
