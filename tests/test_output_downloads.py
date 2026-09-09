"""Tests for Results download / ZIP gating helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from ui.output_panel import _build_zip, _short_paths


def test_build_zip_only_existing_nonzero(tmp_path: Path) -> None:
    good = tmp_path / "final.mp4"
    good.write_bytes(b"abc123")
    empty = tmp_path / "empty.mp4"
    empty.write_bytes(b"")
    missing = tmp_path / "missing.mp4"
    data = _build_zip(
        [
            ("final.mp4", good),
            ("empty.mp4", empty),
            ("missing.mp4", missing),
        ]
    )
    assert data is not None
    import zipfile
    import io

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = set(zf.namelist())
    assert names == {"final.mp4"}


def test_build_zip_none_when_empty(tmp_path: Path) -> None:
    assert _build_zip([]) is None
    empty = tmp_path / "e.mp4"
    empty.write_bytes(b"")
    assert _build_zip([("e.mp4", empty)]) is None


def test_short_paths_from_folders_and_disk(tmp_path: Path) -> None:
    shorts = tmp_path / "renders" / "shorts"
    shorts.mkdir(parents=True)
    a = shorts / "short_15s_00.mp4"
    a.write_bytes(b"x")
    result = {
        "output_files": {
            "folders": {"shorts": [str(a)]},
        }
    }
    found = _short_paths(tmp_path, result)
    assert a in found


def test_quality_probe_failure_does_not_invent_streams(tmp_path: Path) -> None:
    from tools.quality.checks import run_quality_checks

    media = tmp_path / "bad.mp4"
    media.write_bytes(b"garbage")
    with patch("tools.quality.checks.probe_media", return_value=None):
        checks = run_quality_checks(media, require_media=True)
    by_id = {c.id: c for c in checks}
    assert by_id["probe"].passed is False
    assert "validate_video" not in by_id or by_id.get("validate_video") is None
