"""Tests for BrandAgent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.brand_agent import BrandAgent
from config.settings import get_settings
from schemas.brand import BrandPack, BrandPlan, BrandVoice, ColorTheme
from schemas.job import FeatureFlags, SourceType, VideoJobConfig
from schemas.project import ProjectMetadata
from tools.brand.catalog import clear_brand_cache


def test_brand_flag_off_skips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    get_settings.cache_clear()
    clear_brand_cache()
    project_dir = tmp_path / "outputs" / "projects" / "br1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="br1", source_type=SourceType.SCRIPT, raw_text="x"
    )
    result = BrandAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(),
        features=FeatureFlags(brand=False),
    )
    assert result.brand_pack.plan.skipped is True
    data = json.loads(Path(result.brand_path).read_text(encoding="utf-8"))
    assert data["plan"]["skipped"] is True
    get_settings.cache_clear()


def test_brand_writes_json_when_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    get_settings.cache_clear()
    clear_brand_cache()
    project_dir = tmp_path / "outputs" / "projects" / "br2"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="br2", source_type=SourceType.YOUTUBE, source_path="https://x"
    )

    def _build(**_: object) -> BrandPack:
        return BrandPack(
            source_label="Test",
            plan=BrandPlan(
                brand_name="TestCo",
                voice=BrandVoice(tone="friendly"),
                colors=ColorTheme(primary="#111111"),
                provider="heuristic",
                skipped=False,
                notes="test",
            ),
            notes="test",
        )

    result = BrandAgent().run(
        project,
        project_dir=project_dir,
        config=VideoJobConfig(brand_name="TestCo"),
        features=FeatureFlags(brand=True),
        build_fn=_build,
    )
    assert result.brand_pack.plan.skipped is False
    path = Path(result.brand_path)
    assert path.name == "brand_plan.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["plan"]["brand_name"] == "TestCo"
    public = result.public_output()
    assert set(public.keys()) == {
        "voice",
        "visual_identity",
        "colors",
        "cta",
        "messaging",
    }
    get_settings.cache_clear()
