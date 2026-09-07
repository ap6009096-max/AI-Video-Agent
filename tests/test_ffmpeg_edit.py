"""Tests for FFmpeg edit helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from tools.ffmpeg.edit import concat_segments, cut_segment


def test_cut_segment_missing_media(tmp_path: Path) -> None:
    out = tmp_path / "out.mp4"
    assert cut_segment(tmp_path / "missing.mp4", out, start=0.0, end=1.0) is None


def test_cut_segment_invalid_range(tmp_path: Path) -> None:
    media = tmp_path / "in.mp4"
    media.write_bytes(b"fake")
    assert cut_segment(media, tmp_path / "out.mp4", start=2.0, end=1.0) is None


def test_cut_segment_success_mocked(tmp_path: Path) -> None:
    media = tmp_path / "in.mp4"
    media.write_bytes(b"fake")
    out = tmp_path / "out.mp4"

    def _fake_run(args: list[str]) -> bool:
        Path(args[-1]).write_bytes(b"ok")
        return True

    with patch("tools.ffmpeg.edit.run_ffmpeg", side_effect=_fake_run):
        result = cut_segment(media, out, start=0.0, end=1.5)
    assert result is not None
    assert result.is_file()


def test_concat_segments_empty() -> None:
    assert concat_segments([], Path("out.mp4")) is None


def test_concat_single_mocked(tmp_path: Path) -> None:
    seg = tmp_path / "a.mp4"
    seg.write_bytes(b"a")
    out = tmp_path / "joined.mp4"

    def _fake_run(args: list[str]) -> bool:
        Path(args[-1]).write_bytes(b"joined")
        return True

    with patch("tools.ffmpeg.edit.run_ffmpeg", side_effect=_fake_run):
        result = concat_segments([seg], out)
    assert result is not None
    assert result.read_bytes() == b"joined"
