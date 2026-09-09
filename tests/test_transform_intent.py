"""Tests for Phase 1 selective scene transform intent."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from agents.transform_intent_agent import TransformIntentAgent
from config.settings import get_settings
from schemas.job import FeatureFlags, SourceType, VideoJobConfig
from schemas.project import ProjectMetadata
from schemas.transform_intent import GeminiTransformBatch, TransformIntent
from tools.transform.catalog import parse_transform_heuristic
from tools.transform.selective import resolve_scene_window


def test_heuristic_changed_vs_preserved() -> None:
    scenes = {
        "scenes": [
            {"scene_id": "s1", "start": 0.0, "end": 10.0},
            {"scene_id": "s2", "start": 10.0, "end": 25.0},
            {"scene_id": "s3", "start": 25.0, "end": 40.0},
        ]
    }
    intent = parse_transform_heuristic(
        instruction=(
            "Make the guest's answer in scene 3 shorter and funnier. "
            "Keep the host, background, music, and all other scenes unchanged."
        ),
        target_scene=3,
        scenes=scenes,
    )
    assert intent.target_scene == 3
    assert intent.target_speaker == "guest"
    assert intent.scenes_total == 3
    assert intent.scenes_changed == 1
    assert intent.scenes_preserved == 2
    assert any("shorten" in c or "funnier" in c for c in intent.requested_changes)
    assert "dialogue" in intent.regeneration_scope or "voice" in intent.regeneration_scope
    assert "other_scenes" in intent.preserved_elements
    assert "music" in intent.preserved_elements


def test_resolve_scene_window() -> None:
    scenes = {
        "scenes": [
            {"start": 0.0, "end": 5.0},
            {"start": 5.0, "end": 12.0},
            {"start": 12.0, "end": 20.0},
        ]
    }
    start, end, idx = resolve_scene_window(scenes, 3)
    assert idx == 2
    assert start == 12.0
    assert end == 20.0


def test_agent_writes_transform_intent_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "ti1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="ti1", source_type=SourceType.UPLOAD, upload_path="x.mp4"
    )

    def _fake(**_: object) -> GeminiTransformBatch:
        return GeminiTransformBatch(
            target_scene=2,
            target_speaker="guest",
            requested_changes=["shorten dialogue", "make dialogue funnier"],
            preserved_elements=["host", "background", "music", "other_scenes"],
            regeneration_scope=["dialogue", "voice"],
            unsupported_changes=[],
            notes="test",
        )

    result = TransformIntentAgent().run(
        project,
        project_dir=project_dir,
        features=FeatureFlags(scene_transform=True),
        config=VideoJobConfig(
            transform_instruction="Make scene 2 shorter and funnier",
            transform_scene_id="2",
        ),
        scenes={
            "scenes": [
                {"start": 0, "end": 5},
                {"start": 5, "end": 15},
                {"start": 15, "end": 30},
            ]
        },
        analyze_fn=_fake,
    )
    path = Path(result.transform_intent_path)
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["plan"]["skipped"] is False
    assert data["plan"]["intent"]["scenes_changed"] == 1
    assert data["plan"]["intent"]["scenes_preserved"] == 2
    public = result.public_output()
    assert "Changed 1 of 3 scenes" in public["changed_summary"]
    get_settings.cache_clear()


def test_agent_flag_off_without_instruction_skips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "ti2"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="ti2", source_type=SourceType.SCRIPT, raw_text="x"
    )
    result = TransformIntentAgent().run(
        project,
        project_dir=project_dir,
        features=FeatureFlags(scene_transform=False),
        config=VideoJobConfig(),
    )
    assert result.transform_intent_pack.plan.skipped is True
    get_settings.cache_clear()


def test_selective_stitch_records_changed_scene(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    from agents.render_agent import RenderAgent

    project_dir = tmp_path / "outputs" / "projects" / "rd_ti"
    project_dir.mkdir(parents=True)
    source = project_dir / "source" / "input.mp4"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"fake-mp4")
    project = ProjectMetadata(
        project_id="rd_ti",
        source_type=SourceType.UPLOAD,
        upload_path=str(source),
    )
    intent = TransformIntent(
        target_scene=2,
        instruction="shorten scene 2",
        requested_changes=["shorten dialogue"],
        preserved_elements=["other_scenes", "music"],
        regeneration_scope=["dialogue", "trim"],
        start_seconds=5.0,
        end_seconds=15.0,
        scenes_total=3,
        scenes_changed=1,
    )
    pack = {
        "plan": {
            "skipped": False,
            "intent": intent.model_dump(mode="json"),
        }
    }

    def _fake_cut(media: Path, dest: Path, *, start: float, end: float) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(f"cut-{start}-{end}".encode())
        return dest

    def _fake_concat(segments: list[Path], dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"joined")
        return dest

    def _fake_encode(src: Path, dest: Path, **_: object) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes() if src.is_file() else b"enc")
        return dest

    with (
        patch("agents.render_agent.resolve_ffmpeg_binary", lambda: "ffmpeg"),
        patch("agents.render_agent.cut_segment", _fake_cut),
        patch("agents.render_agent.concat_segments", _fake_concat),
        patch("agents.render_agent.encode_mp4", _fake_encode),
        patch("tools.transform.selective.cut_segment", _fake_cut),
        patch("tools.transform.selective.concat_segments", _fake_concat),
        patch("tools.transform.selective.probe_media", lambda *_a, **_k: {"duration": 40.0}),
        patch("agents.render_agent.normalize_loudness", lambda *a, **k: None),
        patch("agents.render_agent.resize", lambda *a, **k: None),
        patch("agents.render_agent.burn_subtitles", lambda *a, **k: None),
        patch("agents.render_agent.extract_thumbnail", lambda *a, **k: None),
        patch.object(RenderAgent, "_resolve_source", lambda self, *a, **k: source),
    ):
        result = RenderAgent().run(
            project,
            project_dir=project_dir,
            config=VideoJobConfig(platform="YouTube Shorts"),
            features=FeatureFlags(multi_shorts_export=True, scene_transform=True),
            transform_intent_pack=pack,
            scenes={
                "scenes": [
                    {"start": 0, "end": 5},
                    {"start": 5, "end": 15},
                    {"start": 15, "end": 40},
                ]
            },
        )

    plan = json.loads(Path(result.render_path).read_text(encoding="utf-8"))["plan"]
    op_names = [o["name"] for o in plan.get("ops") or []]
    assert "selective_stitch" in op_names or "extract_changed" in op_names
    assert Path(plan["output_path"]).name == "final.mp4"
    get_settings.cache_clear()


def test_quality_blocks_empty_file(tmp_path: Path) -> None:
    from tools.quality.checks import run_quality_checks

    empty = tmp_path / "empty.mp4"
    empty.write_bytes(b"")
    checks = run_quality_checks(empty, require_media=True)
    by_id = {c.id: c for c in checks}
    assert by_id["file_exists"].passed is True
    assert by_id["file_size"].passed is False


def test_scene_transformation_enables_shorts() -> None:
    from core.mode_mapper import map_mode_to_config

    flags, cfg = map_mode_to_config("Scene Transformation")
    assert flags.scene_transform is True
    assert flags.multi_shorts_export is True
    assert 30 in cfg.short_durations
