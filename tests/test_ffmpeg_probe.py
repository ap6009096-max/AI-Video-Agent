"""Tests for FFmpeg probe helper."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from tools.ffmpeg.probe import probe_media


def test_probe_missing_file(tmp_path: Path) -> None:
    assert probe_media(tmp_path / "nope.mp4") is None


def test_probe_ffprobe_json(tmp_path: Path) -> None:
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"x")
    payload = """{
      "format": {"duration": "3.5"},
      "streams": [
        {
          "codec_type": "video",
          "codec_name": "h264",
          "width": 1280,
          "height": 720,
          "avg_frame_rate": "24/1"
        },
        {
          "codec_type": "audio",
          "codec_name": "aac",
          "sample_rate": "48000"
        }
      ]
    }"""
    proc = MagicMock(returncode=0, stdout=payload)
    with (
        patch("tools.ffmpeg.probe.resolve_ffprobe_binary", return_value="ffprobe"),
        patch("tools.ffmpeg.probe.subprocess.run", return_value=proc),
    ):
        info = probe_media(media)
    assert info is not None
    assert info["duration"] == 3.5
    assert info["width"] == 1280
    assert info["height"] == 720
    assert info["has_audio"] is True
    assert info["video_codec"] == "h264"
    assert info["fps"] == 24.0
    assert info["audio_sample_rate"] == 48000
