"""Tests for Creator OS stage registry and presets."""

from __future__ import annotations

from graph.workflow import STEP_NODE_NAMES
from schemas.creator_os import (
    CREATOR_CAPABILITY_PRESET,
    CREATOR_OS_STAGES,
    NODE_TO_STAGE,
    STAGE_IDS,
    apply_creator_os_preset,
    stage_for_node,
    stage_progress_from_state,
)
from schemas.job import FeatureFlags, ProgressStepStatus, SourceType
from ui.feature_toggles import merge_creator_os_preset


def test_creator_os_stage_order() -> None:
    ids = [s[0] for s in CREATOR_OS_STAGES]
    assert ids == list(STAGE_IDS)
    assert ids[0] == "research"
    assert ids[-1] == "publishing_preparation"
    assert "analytics" in ids
    assert ids.index("analytics") < ids.index("publishing_preparation")


def test_every_step_node_maps_to_stage() -> None:
    missing = [n for n in STEP_NODE_NAMES if n not in NODE_TO_STAGE]
    assert missing == [], f"Unmapped STEP_NODE_NAMES: {missing}"


def test_stage_for_node() -> None:
    assert stage_for_node("research") == "research"
    assert stage_for_node("script") == "script"
    assert stage_for_node("export") == "publishing_preparation"
    assert stage_for_node("analytics") == "analytics"
    assert stage_for_node("") is None


def test_creator_capability_preset_flags() -> None:
    preset = apply_creator_os_preset()
    for key in (
        "research",
        "storyboard",
        "video_generation",
        "seo",
        "thumbnail",
        "content_calendar",
        "analytics",
        "platform_optimization",
        "captions",
        "smart_clip_detection",
    ):
        assert preset[key] is True
        assert key in CREATOR_CAPABILITY_PRESET or key in FeatureFlags().model_dump()
    flags = FeatureFlags.model_validate(preset)
    assert flags.research is True
    assert flags.analytics is True


def test_merge_creator_os_preset_helper() -> None:
    merged = merge_creator_os_preset({"research": False, "seo": False})
    assert merged["research"] is True
    assert merged["seo"] is True


def test_stage_progress_completed_job() -> None:
    rows = stage_progress_from_state({"status": "completed"})
    assert len(rows) == len(STAGE_IDS)
    assert all(r["status"] == ProgressStepStatus.COMPLETED.value for r in rows)


def test_stage_progress_running_with_last_node() -> None:
    rows = stage_progress_from_state(
        {
            "status": "running",
            "last_node": "script",
            "scripts": {"scripts": [{"title": "x"}]},
        }
    )
    by_id = {r["id"]: r["status"] for r in rows}
    assert by_id["script"] == ProgressStepStatus.RUNNING.value
    assert by_id["research"] == ProgressStepStatus.COMPLETED.value
    assert by_id["publishing_preparation"] == ProgressStepStatus.PENDING.value


def test_stage_progress_pack_signals() -> None:
    rows = stage_progress_from_state(
        {
            "status": "running",
            "research_report": {"topic": "Sleep"},
            "export_pack": {"export_path": "manifest.json"},
        }
    )
    by_id = {r["id"]: r["status"] for r in rows}
    assert by_id["research"] in {
        ProgressStepStatus.COMPLETED.value,
        ProgressStepStatus.RUNNING.value,
    }
    assert by_id["publishing_preparation"] in {
        ProgressStepStatus.COMPLETED.value,
        ProgressStepStatus.RUNNING.value,
    }


def test_idea_source_type_exists() -> None:
    assert SourceType.IDEA.value == "idea"
