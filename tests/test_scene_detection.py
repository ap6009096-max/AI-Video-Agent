"""Unit tests for fused scene detection merge/caps."""

from __future__ import annotations

from tools.video.scene_detect import build_detected_scenes, describe_scene, detect_scenes


def test_describe_scene_templates() -> None:
    assert "Hard cut" in describe_scene(["cut"], 0.62)
    assert "Speaker pause" in describe_scene(["speaker"], 0.4)
    assert describe_scene([], 0.0) == "Stable visual segment"


def test_merge_min_duration() -> None:
    candidates = [
        {"time": 0.5, "score": 0.9, "kinds": ["cut"]},
        {"time": 1.0, "score": 0.8, "kinds": ["cut"]},
        {"time": 5.0, "score": 0.7, "kinds": ["cut"]},
    ]
    scenes = build_detected_scenes(
        candidates,
        duration=10.0,
        min_duration=1.5,
        min_gap=0.4,
        max_scenes=120,
    )
    assert all(s.duration >= 1.5 or s.id == len(scenes) - 1 for s in scenes[:-1])
    assert scenes[0].start == 0.0
    assert scenes[-1].end == 10.0
    assert all(s.description for s in scenes)


def test_max_scenes_cap_keeps_strongest() -> None:
    candidates = [
        {"time": float(i), "score": float(i) / 100.0, "kinds": ["cut"]}
        for i in range(1, 50)
    ]
    scenes = build_detected_scenes(
        candidates,
        duration=60.0,
        min_duration=0.1,
        min_gap=0.05,
        max_scenes=5,
    )
    assert len(scenes) <= 5


def test_speaker_gap_from_speech_transcript() -> None:
    result = detect_scenes(
        analysis={
            "properties": {"duration_seconds": 20.0},
            "visual_changes": [],
            "scenes": [],
        },
        speech_transcript={
            "segments": [
                {"start": 0.0, "end": 2.0, "text": "a"},
                {"start": 5.0, "end": 7.0, "text": "b"},
            ]
        },
        speaker_gap=1.25,
        min_duration=0.5,
        min_gap=0.2,
        max_scenes=50,
    )
    assert result["source_signals"]["speaker"] >= 1
    kinds = {k for s in result["scenes"] for k in s.change_kinds}
    assert "speaker" in kinds
    for scene in result["scenes"]:
        assert scene.duration == scene.end - scene.start
        assert hasattr(scene, "visual_change_score")


def test_reuse_analysis_visual_changes_no_media() -> None:
    result = detect_scenes(
        analysis={
            "properties": {"duration_seconds": 12.0},
            "visual_changes": [
                {"time_seconds": 3.0, "score": 0.7, "kind": "cut"},
                {"time_seconds": 8.0, "score": 0.4, "kind": "motion"},
            ],
            "scenes": [{"id": 0, "start": 0.0, "end": 3.0, "score": 0.0}],
            "object_cues": [
                {"label": "motion_hotspot", "time_seconds": 8.0, "detail": "x"}
            ],
        },
        min_duration=1.0,
        min_gap=0.3,
        max_scenes=50,
    )
    assert result["source_signals"]["visual"] >= 1
    assert len(result["scenes"]) >= 2
    assert all(s.visual_change_score >= 0 for s in result["scenes"])
