"""Tests for project layout dual-write."""

from __future__ import annotations

import json
from pathlib import Path

from tools.project.layout import ensure_project_layout, finalize_project_layout


def test_ensure_and_finalize_aliases(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    dirs = ensure_project_layout(root)
    assert dirs["final"].is_dir()
    assert dirs["subtitles"].is_dir()

    analysis = root / "analysis"
    analysis.mkdir(parents=True, exist_ok=True)
    (analysis / "scenes.json").write_text("{}", encoding="utf-8")
    (analysis / "video_analysis.json").write_text("{}", encoding="utf-8")
    (analysis / "moments.json").write_text("{}", encoding="utf-8")
    (analysis / "clips.json").write_text("{}", encoding="utf-8")
    (analysis / "quality_report.json").write_text(
        json.dumps({"passed": True}), encoding="utf-8"
    )
    (root / "project.json").write_text("{}", encoding="utf-8")

    out = finalize_project_layout(root, state={})
    assert (root / "scenes.json").is_file()
    assert (root / "analysis.json").is_file()
    assert (root / "localization.json").is_file()
    assert (root / "video_plan.json").is_file()
    assert (root / "quality_report.json").is_file()
    assert "aliases" in out
