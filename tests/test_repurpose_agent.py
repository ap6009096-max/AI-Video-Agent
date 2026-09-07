"""Tests for RepurposeAgent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.repurpose_agent import RepurposeAgent
from config.settings import get_settings
from schemas.job import FeatureFlags, SourceType, VideoJobConfig
from schemas.project import ProjectMetadata
from schemas.repurpose import GeminiRepurposeBatch
from tools.repurpose.catalog import clear_repurpose_cache


def test_repurpose_flag_off_skips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    clear_repurpose_cache()
    project_dir = tmp_path / "outputs" / "projects" / "rp1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="rp1", source_type=SourceType.SCRIPT, raw_text="x"
    )
    result = RepurposeAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(platform="YouTube"),
        features=FeatureFlags(repurpose=False),
    )
    assert result.repurpose_pack.plan.skipped is True
    data = json.loads(Path(result.repurpose_path).read_text(encoding="utf-8"))
    assert data["plan"]["skipped"] is True
    get_settings.cache_clear()


def test_repurpose_writes_public_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    clear_repurpose_cache()
    project_dir = tmp_path / "outputs" / "projects" / "rp2"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="rp2", source_type=SourceType.YOUTUBE, source_path="https://x"
    )

    def _fake(**_: object) -> GeminiRepurposeBatch:
        return GeminiRepurposeBatch(
            reels="reel script",
            shorts="shorts script",
            tiktok="tiktok script",
            blog_summary="blog",
            linkedin_post="linkedin",
            twitter_thread=["1/ tip", "2/ tip"],
            instagram_caption="ig #viral",
            newsletter_summary="newsletter",
        )

    result = RepurposeAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(platform="YouTube", repurpose_source="Video"),
        features=FeatureFlags(repurpose=True),
        analyze_fn=_fake,
    )
    plan = result.repurpose_pack.plan
    assert plan.skipped is False
    assert plan.source_kind == "video"
    public = result.public_output()
    assert set(public.keys()) == {
        "source_kind",
        "reels",
        "shorts",
        "tiktok",
        "blog_summary",
        "linkedin_post",
        "twitter_thread",
        "instagram_caption",
        "newsletter_summary",
    }
    assert public["reels"] == "reel script"
    get_settings.cache_clear()
