"""Tests for VO audio sync / replace helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from tools.ffmpeg.audio_ops import replace_audio, sync_voice_to_video


def test_replace_audio_missing_files(tmp_path: Path) -> None:
    assert (
        replace_audio(tmp_path / "a.mp4", tmp_path / "b.mp3", tmp_path / "o.mp4")
        is None
    )


def test_replace_audio_success_mocked(tmp_path: Path) -> None:
    video = tmp_path / "v.mp4"
    audio = tmp_path / "a.mp3"
    out = tmp_path / "o.mp4"
    video.write_bytes(b"video")
    audio.write_bytes(b"audio")

    def _run(args):
        # last arg is output path
        Path(args[-1]).write_bytes(b"muxed")
        return True

    with patch("tools.ffmpeg.audio_ops.run_ffmpeg", side_effect=_run):
        result = replace_audio(video, audio, out)
    assert result is not None
    assert result.is_file()


def test_sync_voice_to_video_mocked(tmp_path: Path) -> None:
    video = tmp_path / "v.mp4"
    voice = tmp_path / "vo.mp3"
    out = tmp_path / "final.mp4"
    video.write_bytes(b"video")
    voice.write_bytes(b"voice")

    def _run(args):
        Path(args[-1]).write_bytes(b"out")
        return True

    with (
        patch(
            "tools.ffmpeg.audio_ops.probe_media",
            return_value={"duration": 2.5, "has_audio": True},
        ),
        patch("tools.ffmpeg.audio_ops.run_ffmpeg", side_effect=_run),
    ):
        result = sync_voice_to_video(video, voice, out)
    assert result is not None
    assert result.is_file()
