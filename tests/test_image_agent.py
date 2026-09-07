"""Tests for ImageAgent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.image_agent import ImageAgent
from config.settings import get_settings
from schemas.image import GeminiImageBatch, GeminiImageItem
from schemas.job import FeatureFlags, SourceType, VideoJobConfig
from schemas.project import ProjectMetadata
from tools.images.catalog import clear_image_cache
from tools.images.generate import write_placeholder_png


def test_image_flag_off_skips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    clear_image_cache()
    project_dir = tmp_path / "outputs" / "projects" / "img1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="img1", source_type=SourceType.SCRIPT, raw_text="x"
    )
    result = ImageAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(platform="YouTube"),
        features=FeatureFlags(image_generation=False),
    )
    assert result.image_pack.plan.skipped is True
    data = json.loads(Path(result.image_path).read_text(encoding="utf-8"))
    assert data["plan"]["skipped"] is True
    get_settings.cache_clear()


def test_image_writes_public_fields_and_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    clear_image_cache()
    project_dir = tmp_path / "outputs" / "projects" / "img2"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="img2", source_type=SourceType.SCRIPT, raw_text="x"
    )

    def _fake(**_: object) -> GeminiImageBatch:
        return GeminiImageBatch(
            items=[
                GeminiImageItem(
                    scene_id="thumb_1",
                    prompt="Bold thumbnail with forest trail",
                    style="Bold",
                    environment="Wildlife/Nature Forest",
                    kind="thumbnail",
                ),
                GeminiImageItem(
                    scene_id="scene_1",
                    prompt="Cinematic forest still",
                    style="Cinematic",
                    environment="Wildlife/Nature Forest",
                    kind="scene",
                ),
            ]
        )

    result = ImageAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(
            platform="YouTube",
            visual_style="Cinematic",
            environment="Wildlife/Nature Forest",
        ),
        features=FeatureFlags(image_generation=True),
        script_pack={
            "primary": {"title": "Trail tips", "hook": "Mist at dawn"}
        },
        analyze_fn=_fake,
        generate_fn=lambda prompt, dest, **_: (
            write_placeholder_png(Path(dest)),
            "placeholder",
        ),
    )
    plan = result.image_pack.plan
    assert plan.skipped is False
    assert len(plan.items) == 2
    public = result.public_output()
    assert len(public) == 2
    assert set(public[0].keys()) == {
        "scene_id",
        "prompt",
        "style",
        "environment",
        "image_path",
    }
    images_dir = project_dir / "images"
    assert images_dir.is_dir()
    assert any(images_dir.glob("*.png"))
    get_settings.cache_clear()
