"""Architecture refactor smoke tests (nested graphs, caches, gates)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from schemas.project_refs import dual_write_paths, refs_from_project_dir
from tools.analysis.shared_ai import build_shared_ai_analysis, load_shared_ai_analysis
from tools.cache.competitors import get_or_build_competitor_pack
from tools.cache.trends import load_cached_trend, store_cached_trend
from tools.thumbnail.catalog import rank_thumbnail_titles
from tools.vision.face_gate import should_run_face_detection


def test_project_refs_dual_write(tmp_path: Path) -> None:
    root = str(tmp_path)
    update = dual_write_paths(
        {"transcript": {"text": "hi"}},
        project_dir=root,
        written_paths={"transcript": str(tmp_path / "transcripts" / "t.json")},
    )
    assert update["project_dir"] == root
    assert "transcript_path" in update
    assert update["transcript"]["text"] == "hi"
    refs = refs_from_project_dir(root)
    assert refs["shared_ai_analysis_path"].endswith("shared_ai_analysis.json")


def test_shared_ai_analysis_written(tmp_path: Path) -> None:
    report = build_shared_ai_analysis(
        project_dir=tmp_path,
        transcript={"text": "How to grow on YouTube with better hooks and SEO."},
        analyze_fn=None,
    )
    assert (tmp_path / "analysis" / "shared_ai_analysis.json").is_file()
    loaded = load_shared_ai_analysis(tmp_path)
    assert loaded is not None
    assert loaded.get("topics")
    assert report.get("source") == "heuristic"


def test_trend_cache_hit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    from config.settings import get_settings

    get_settings.cache_clear()
    pack = {
        "source_label": "YouTube",
        "plan": {
            "trend_score": 0.7,
            "trend_topics": ["ai"],
            "recommended_tags": ["ai"],
            "trending_hashtags": ["#ai"],
            "trending_keywords": ["ai"],
            "viral_patterns": [],
            "audience_relevance": "",
            "topic_labels": [],
            "platform": "YouTube",
            "provider": "heuristic",
            "skipped": False,
            "notes": "seed",
        },
        "fallback": True,
        "notes": "seed",
    }
    store_cached_trend("YouTube", pack, output_dir=str(tmp_path))
    hit = load_cached_trend("YouTube", output_dir=str(tmp_path), ttl_seconds=86400)
    assert hit is not None
    assert hit["plan"]["trend_score"] == 0.7


def test_face_gate_skips_animation() -> None:
    assert should_run_face_detection("Animation") is False
    assert should_run_face_detection("Screen Recording") is False
    assert should_run_face_detection("Talking Head") is True
    assert should_run_face_detection("Podcast") is True


def test_thumbnail_top3_ctr() -> None:
    titles = [
        "a",
        "You Won't Believe This Tip",
        "Must See: Growth Hacks?",
        "STOP Scrolling — Secrets",
        "plain title here",
    ]
    ranked = rank_thumbnail_titles(titles, emotion="excited", limit=3)
    assert len(ranked) <= 3
    assert ranked


def test_competitor_cache_scaffold(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    from config.settings import get_settings

    get_settings.cache_clear()
    a = get_or_build_competitor_pack(niche="ai shorts", platform="YouTube", topics=["hooks"])
    b = get_or_build_competitor_pack(niche="ai shorts", platform="YouTube", topics=["hooks"])
    assert a.get("competitors")
    assert b.get("cache_hit") is True


def test_main_graph_and_pipelines_compile() -> None:
    from graph.main import build_main_graph
    from graph.pipelines.input_pipeline import build_input_pipeline
    from graph.workflow import WorkflowState, build_flat_video_graph

    flat = build_flat_video_graph()
    assert flat is not None
    main = build_main_graph(flat_graph=flat)
    assert main is not None
    assert build_input_pipeline(WorkflowState) is not None


def test_path_only_slim_roundtrip(tmp_path: Path) -> None:
    from graph.rehydrate import rehydrate_state_from_disk
    from graph.state_slim import slim_state_for_checkpoint

    analysis = tmp_path / "analysis"
    analysis.mkdir(parents=True)
    (analysis / "seo_plan.json").write_text(
        json.dumps({"plan": {"title": "T"}}), encoding="utf-8"
    )
    fat = {
        "project_dir": str(tmp_path),
        "seo_pack": {"plan": {"title": "T"}},
        "transcript": {"text": "huge"},
    }
    slim = slim_state_for_checkpoint(fat)
    assert "seo_pack" not in slim
    assert slim.get("seo_path")
    rehydrated = rehydrate_state_from_disk(slim, tmp_path)
    assert rehydrated.get("seo_pack", {}).get("plan", {}).get("title") == "T"


def test_project_metadata_rehydrates_and_preserves_source_type(tmp_path: Path) -> None:
    from graph.rehydrate import rehydrate_state_from_disk

    (tmp_path / "project.json").write_text(
        json.dumps({"project_id": "p1", "source_type": "youtube", "youtube_url": "u"}),
        encoding="utf-8",
    )
    state = rehydrate_state_from_disk({"project": None}, tmp_path)
    assert state["project"]["source_type"] == "youtube"
    assert state["project"]["youtube_url"] == "u"


def test_empty_project_metadata_recovers_source_type_from_job(tmp_path: Path) -> None:
    from graph.rehydrate import rehydrate_state_from_disk

    (tmp_path / "project.json").write_text("{}", encoding="utf-8")
    state = rehydrate_state_from_disk(
        {"project": None, "job": {"job_id": "p2", "source_type": "upload"}},
        tmp_path,
    )
    assert state["project"]["source_type"] == "upload"


def test_empty_project_metadata_without_job_source_fails_clearly(tmp_path: Path) -> None:
    from core.errors import WorkflowError
    from graph.rehydrate import rehydrate_state_from_disk

    (tmp_path / "project.json").write_text("{}", encoding="utf-8")
    with pytest.raises(WorkflowError, match="source_type is missing"):
        rehydrate_state_from_disk({"project": None, "job": {}}, tmp_path)


def test_whisper_default_tiny() -> None:
    from config.settings import Settings

    s = Settings(_env_file=None)
    assert s.whisper_model == "tiny"


def test_provider_registry() -> None:
    from plugins import get_provider_registry

    reg = get_provider_registry()
    names = reg.list_providers()
    assert "local_stub" in names["voice"]
    assert reg.get_voice("local_stub") is not None


def test_layout_includes_cache_logs(tmp_path: Path) -> None:
    from tools.project.layout import ensure_project_layout

    paths = ensure_project_layout(tmp_path)
    assert paths["cache"].is_dir()
    assert paths["logs"].is_dir()
