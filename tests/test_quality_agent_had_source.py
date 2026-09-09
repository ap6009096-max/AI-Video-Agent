"""QualityAgent had_source / soft-skip honesty."""

from __future__ import annotations

from pathlib import Path

import pytest

from agents.quality_agent import QualityAgent
from core.errors import QualityAgentError
from schemas.job import SourceType
from schemas.project import ProjectMetadata


def test_had_source_true_when_path_recorded_but_file_missing(tmp_path: Path) -> None:
    """Recorded source_path counts even if the file is gone (moved/restored)."""
    root = tmp_path / "proj"
    root.mkdir()
    missing = tmp_path / "gone" / "source.mp4"  # never created
    render_pack = {
        "plan": {
            "skipped": True,
            "encoded": False,
            "source_path": str(missing),
            "output_path": "",
        }
    }
    agent = QualityAgent()
    media, *_rest, skipped, had_source = agent._resolve_expectations(
        root, render_pack, None
    )
    assert skipped is True
    assert had_source is True
    assert media is None


def test_quality_fail_closed_when_source_path_recorded_but_missing(
    tmp_path: Path,
) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    missing = str(tmp_path / "does_not_exist.mp4")
    project = ProjectMetadata(
        project_id="q-had-src",
        source_type=SourceType.UPLOAD,
        source_path=missing,
    )
    render_pack = {
        "plan": {
            "skipped": True,
            "encoded": False,
            "source_path": missing,
            "output_path": "",
        }
    }
    with pytest.raises(QualityAgentError, match="source media present"):
        QualityAgent().run(
            project,
            project_dir=root,
            render_pack=render_pack,
        )


def test_quality_fail_closed_post_encode_validation_plan(tmp_path: Path) -> None:
    """Post-encode validate failure: skipped=False, encoded=False — not soft-skip."""
    root = tmp_path / "proj"
    root.mkdir()
    src = str(tmp_path / "source.mp4")
    project = ProjectMetadata(
        project_id="q-post-enc",
        source_type=SourceType.UPLOAD,
        source_path=src,
    )
    render_pack = {
        "plan": {
            "skipped": False,
            "encoded": False,
            "source_path": src,
            "output_path": "",
            "notes": "Full video generation failed. Stage: Render. Reason: invalid",
        }
    }
    with pytest.raises(QualityAgentError, match="source media present"):
        QualityAgent().run(
            project,
            project_dir=root,
            render_pack=render_pack,
        )


def test_quality_soft_skip_when_no_source_path_recorded(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    project = ProjectMetadata(
        project_id="q-script",
        source_type=SourceType.SCRIPT,
        source_path="",
    )
    render_pack = {
        "plan": {
            "skipped": True,
            "encoded": False,
            "source_path": "",
            "output_path": "",
        }
    }
    result = QualityAgent().run(
        project,
        project_dir=root,
        render_pack=render_pack,
    )
    assert result.quality_pack.report.skipped is True
    assert result.quality_pack.report.passed is True
