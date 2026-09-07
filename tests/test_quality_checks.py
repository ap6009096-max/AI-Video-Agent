"""Tests for quality checks and correction path."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from schemas.quality import QualityCheck
from tools.quality.checks import attempt_corrections, run_quality_checks


def test_quality_file_missing(tmp_path: Path) -> None:
    checks = run_quality_checks(tmp_path / "missing.mp4", require_media=True)
    assert checks
    assert checks[0].id == "file_exists"
    assert checks[0].passed is False


def test_quality_soft_skip_no_media() -> None:
    checks = run_quality_checks(None, require_media=False)
    assert len(checks) == 1
    assert checks[0].passed is True


def test_aspect_mismatch_detection(tmp_path: Path) -> None:
    media = tmp_path / "v.mp4"
    media.write_bytes(b"x")
    fake = {
        "duration": 2.0,
        "width": 1920,
        "height": 1080,
        "fps": 30.0,
        "video_codec": "h264",
        "audio_codec": "aac",
        "audio_sample_rate": 48000,
        "has_audio": True,
        "has_video": True,
        "container": "mp4",
    }
    with (
        patch("tools.quality.checks.probe_media", return_value=fake),
        patch("tools.quality.checks._sample_frames", return_value=(True, True, "ok")),
    ):
        checks = run_quality_checks(
            media,
            expect_width=1080,
            expect_height=1920,
            expect_aspect="9:16",
        )
    by_id = {c.id: c for c in checks}
    assert by_id["aspect_ratio"].passed is False
    assert by_id["resolution"].passed is False


def test_attempt_corrections_reencode(tmp_path: Path) -> None:
    media = tmp_path / "bad.mp4"
    media.write_bytes(b"x")
    out = tmp_path / "fixed.mp4"
    checks = [
        QualityCheck(id="resolution", passed=False, message="bad res"),
        QualityCheck(id="fps", passed=False, message="bad fps"),
    ]

    def _fake_encode(src, dest, **kwargs):
        Path(dest).write_bytes(b"fixed")
        return Path(dest)

    with patch("tools.quality.checks.encode_mp4", side_effect=_fake_encode):
        fixed, names = attempt_corrections(
            media, checks, out_path=out, expect_width=1080, expect_height=1920
        )
    assert fixed is not None
    assert "reencode_mp4" in names
