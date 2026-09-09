"""Tests for strict validate_video (fail closed)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from tools.media.validate_video import validate_video


def test_validate_missing(tmp_path: Path) -> None:
    result = validate_video(tmp_path / "nope.mp4")
    assert result.ok is False
    assert "exist" in result.reason.lower() or "No media" in result.reason


def test_validate_empty_file(tmp_path: Path) -> None:
    empty = tmp_path / "empty.mp4"
    empty.write_bytes(b"")
    result = validate_video(empty)
    assert result.ok is False
    assert "empty" in result.reason.lower()


def test_validate_garbage_bytes(tmp_path: Path) -> None:
    garbage = tmp_path / "garbage.mp4"
    garbage.write_bytes(b"not-a-real-video-file")
    result = validate_video(garbage)
    assert result.ok is False


def test_validate_real_mp4_when_ffmpeg_available(tmp_path: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("ffmpeg not on PATH")
    out = tmp_path / "tiny.mp4"
    proc = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=320x240:d=0.5",
            "-f",
            "lavfi",
            "-i",
            "sine=f=440:d=0.5",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(out),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    if proc.returncode != 0 or not out.is_file():
        pytest.skip(f"could not generate fixture MP4: {proc.stderr[:200]}")
    result = validate_video(out)
    assert result.ok is True
    assert result.duration > 0
    assert result.width > 0
    assert result.height > 0
    assert result.fps > 0
    assert result.has_video is True
