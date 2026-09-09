"""Tests for RenderAgent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.render_agent import RenderAgent
from config.settings import get_settings
from schemas.job import SourceType, VideoJobConfig
from schemas.project import ProjectMetadata


def test_render_agent_plan_soft_skip_without_media(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "rd1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="rd1", source_type=SourceType.SCRIPT, raw_text="hello"
    )
    result = RenderAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(platform="TikTok", reframe_aspect="9:16"),
        platform_pack={
            "plan": {
                "metadata": {"aspect_recommendation": "9:16"},
                "export_hints": {"preferred_aspect": "9:16"},
            }
        },
    )
    path = Path(result.render_path)
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["plan"]["skipped"] is True
    assert data["plan"]["encoded"] is False
    assert data["plan"]["target_aspect"] == "9:16"
    get_settings.cache_clear()


def test_render_post_encode_validation_failure_not_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """validate_video fail after encode must set encoded=False, skipped=False."""
    from unittest.mock import MagicMock, patch

    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "rd_val"
    project_dir.mkdir(parents=True)
    source = project_dir / "source.mp4"
    source.write_bytes(b"fake-mp4")
    project = ProjectMetadata(
        project_id="rd_val",
        source_type=SourceType.UPLOAD,
        source_path=str(source),
    )

    def _fake_encode(src, dst, **_kwargs):
        Path(dst).write_bytes(b"encoded-bytes")
        return Path(dst)

    fake_validation = MagicMock(ok=False, reason="not a playable video")

    with (
        patch("agents.render_agent.resolve_ffmpeg_binary", return_value="ffmpeg"),
        patch("agents.render_agent.encode_mp4", side_effect=_fake_encode),
        patch("agents.render_agent.validate_video", return_value=fake_validation),
        patch("agents.render_agent.extract_thumbnail", return_value=None),
    ):
        result = RenderAgent().run(
            project,
            project_dir=project_dir,
            config=VideoJobConfig(platform="TikTok"),
            source_metadata={"local_media_path": str(source)},
        )
    plan = result.render_pack.plan
    assert plan.encoded is False
    assert plan.skipped is False
    assert plan.output_path == ""
    assert "Full video generation failed" in (plan.notes or "")
    get_settings.cache_clear()
