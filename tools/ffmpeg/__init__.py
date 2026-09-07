"""Unified FFmpeg tool layer."""

from tools.ffmpeg.audio_ops import ensure_audio_stream, normalize_loudness
from tools.ffmpeg.bin import resolve_ffmpeg_binary, resolve_ffprobe_binary
from tools.ffmpeg.edit import concat_segments, cut_segment
from tools.ffmpeg.encode import convert_format, encode_mp4
from tools.ffmpeg.probe import probe_media
from tools.ffmpeg.subs import burn_subtitles, mux_soft_subs
from tools.ffmpeg.thumb import extract_thumbnail
from tools.ffmpeg.transform import reframe_crop_scale, resize

__all__ = [
    "burn_subtitles",
    "concat_segments",
    "convert_format",
    "cut_segment",
    "encode_mp4",
    "ensure_audio_stream",
    "extract_thumbnail",
    "mux_soft_subs",
    "normalize_loudness",
    "probe_media",
    "reframe_crop_scale",
    "resize",
    "resolve_ffmpeg_binary",
    "resolve_ffprobe_binary",
]
