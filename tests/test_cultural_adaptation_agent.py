"""Tests for CulturalAdaptationAgent with mocked Gemini."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.cultural_adaptation_agent import CulturalAdaptationAgent
from config.settings import get_settings
from schemas.job import FeatureFlags, SourceType, VideoJobConfig
from schemas.localization import (
    GeminiCulturalBatch,
    GeminiCulturalFinding,
    LocalePack,
    LocalizationTarget,
)
from schemas.project import ProjectMetadata
from schemas.story import ClipScript, ScriptsReport


def _fake_analyze(script_blocks, **_kwargs) -> GeminiCulturalBatch:
    assert script_blocks
    return GeminiCulturalBatch(
        findings=[
            GeminiCulturalFinding(
                clip_id=0,
                kind="idiom",
                source_span="home run",
                risk="US sports idiom may not land",
                recommendation="Swap to a local success metaphor",
                local_equivalent="sixer",
            )
        ],
        cultural_summary="Replace US sports idioms with local equivalents.",
    )


def test_cultural_agent_writes_findings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "cul1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="cul1", source_type=SourceType.SCRIPT, raw_text="x"
    )
    scripts = ScriptsReport(
        project_id="cul1",
        scripts=[
            ClipScript(
                clip_id=0,
                title="Win",
                hook="This is a home run",
                short_script="This tip is a home run for your week.",
                caption="Win",
                cta="Follow",
            )
        ],
    )
    result = CulturalAdaptationAgent(analyze_fn=_fake_analyze).run(
        project,
        project_dir=project_dir,
        scripts=scripts,
        config=VideoJobConfig(country="India", language="Hindi", audience="Gen Z"),
        features=FeatureFlags(cultural_adaptation=True),
        locale_pack=LocalePack(
            target=LocalizationTarget(country="India", language="Hindi")
        ),
    )
    assert Path(result.cultural_adaptation_path).is_file()
    data = json.loads(Path(result.cultural_adaptation_path).read_text(encoding="utf-8"))
    assert data["findings"]
    assert data["findings"][0]["kind"] == "idiom"
    assert result.locale_pack is not None
    assert "sports" in result.locale_pack.cultural_summary.lower() or result.locale_pack.cultural_summary
    get_settings.cache_clear()


def test_cultural_agent_skips_when_flag_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "cul2"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="cul2", source_type=SourceType.SCRIPT, raw_text="x"
    )

    def _should_not_run(*_a, **_k):
        raise AssertionError("Gemini should not run")

    result = CulturalAdaptationAgent(analyze_fn=_should_not_run).run(
        project,
        project_dir=project_dir,
        scripts=ScriptsReport(
            project_id="cul2",
            scripts=[ClipScript(clip_id=0, title="T", short_script="S")],
        ),
        features=FeatureFlags(cultural_adaptation=False),
    )
    assert result.cultural_adaptation.provider == "skipped"
    assert result.cultural_adaptation.findings == []
    get_settings.cache_clear()
