"""Tests for HumorLocalizationAgent modes and regional_humor flag."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.humor_localization_agent import (
    HumorLocalizationAgent,
    resolve_effective_humor_mode,
)
from config.settings import get_settings
from schemas.job import FeatureFlags, SourceType, VideoJobConfig
from schemas.localization import (
    GeminiHumorBatch,
    GeminiHumorPlanItem,
    LocalePack,
    LocalizationTarget,
    RegionProfile,
)
from schemas.project import ProjectMetadata
from schemas.story import ClipScript, ScriptsReport


def _fake_plan(script_blocks, **kwargs) -> GeminiHumorBatch:
    assert script_blocks
    assert kwargs.get("mode") in ("original", "localized", "regional")
    return GeminiHumorBatch(
        items=[
            GeminiHumorPlanItem(
                clip_id=0,
                source_humor_present=True,
                strategy="adapt" if kwargs.get("mode") != "original" else "keep",
                rationale="Light joke present",
                suggested_approach="Keep meaning; adapt only if natural",
            )
        ],
        humor_summary="Do not force jokes; adapt only when natural.",
    )


def test_resolve_effective_mode_regional_flag() -> None:
    assert (
        resolve_effective_humor_mode(
            humor_adaptation="none",
            regional_humor_flag=True,
            has_region_profile=True,
        )
        == "regional"
    )
    assert (
        resolve_effective_humor_mode(
            humor_adaptation="regional",
            regional_humor_flag=False,
            has_region_profile=False,
        )
        == "localized"
    )
    assert (
        resolve_effective_humor_mode(
            humor_adaptation="original",
            regional_humor_flag=True,
            has_region_profile=True,
        )
        == "original"
    )


def test_humor_mode_none_no_gemini(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "hum1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="hum1", source_type=SourceType.SCRIPT, raw_text="x"
    )

    def _should_not_run(*_a, **_k):
        raise AssertionError("Gemini should not run for none")

    result = HumorLocalizationAgent(plan_fn=_should_not_run).run(
        project,
        project_dir=project_dir,
        scripts=ScriptsReport(
            project_id="hum1",
            scripts=[ClipScript(clip_id=0, title="T", short_script="Serious tip.")],
        ),
        config=VideoJobConfig(humor_adaptation="none"),
        features=FeatureFlags(regional_humor=False),
    )
    assert result.humor_localization.mode == "none"
    assert result.humor_localization.items[0].strategy == "keep"
    assert "force" in result.humor_localization.humor_summary.lower() or "no humor" in result.humor_localization.humor_summary.lower() or "none" in result.humor_localization.notes.lower()
    get_settings.cache_clear()


def test_humor_localized_writes_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "hum2"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="hum2", source_type=SourceType.SCRIPT, raw_text="x"
    )
    result = HumorLocalizationAgent(plan_fn=_fake_plan).run(
        project,
        project_dir=project_dir,
        scripts=ScriptsReport(
            project_id="hum2",
            scripts=[
                ClipScript(
                    clip_id=0,
                    title="Joke",
                    hook="Funny opener",
                    short_script="A light joke about Mondays.",
                )
            ],
        ),
        config=VideoJobConfig(
            country="India",
            humor_adaptation="localized",
            humor_style="Wholesome",
            audience="Gen Z",
        ),
        locale_pack=LocalePack(
            target=LocalizationTarget(country="India", language="Hindi")
        ),
    )
    path = Path(result.humor_localization_path)
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["mode"] == "localized"
    assert data["items"][0]["strategy"] in (
        "keep",
        "adapt",
        "neutralize",
        "drop_joke_keep_meaning",
    )
    assert result.locale_pack is not None
    assert result.locale_pack.humor_summary
    get_settings.cache_clear()


def test_regional_humor_flag_forces_regional(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "hum3"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="hum3", source_type=SourceType.SCRIPT, raw_text="x"
    )
    pack = LocalePack(
        target=LocalizationTarget(
            country="India", region="Gujarat", language="Gujarati"
        ),
        region=RegionProfile(
            id="in-gujarat",
            country_id="in",
            name="Gujarat",
            language="Gujarati",
            humor_notes="Family-friendly",
        ),
    )
    result = HumorLocalizationAgent(plan_fn=_fake_plan).run(
        project,
        project_dir=project_dir,
        scripts=ScriptsReport(
            project_id="hum3",
            scripts=[ClipScript(clip_id=0, title="T", short_script="Ha")],
        ),
        config=VideoJobConfig(humor_adaptation="none", country="India", region="Gujarat"),
        features=FeatureFlags(regional_humor=True),
        locale_pack=pack,
    )
    assert result.humor_localization.mode == "regional"
    get_settings.cache_clear()
