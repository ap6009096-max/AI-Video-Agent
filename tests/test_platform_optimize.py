"""Tests for platform optimize / metadata builder."""

from __future__ import annotations

from tools.platforms.optimize import build_platform_pack


SCRIPTS = {
    "scripts": [
        {
            "title": "How to win at short form video marketing tips forever",
            "hook": "Stop scrolling — this changes everything",
            "caption": "A short caption about tips.",
            "cta": "Follow for more",
            "thumbnail_text": "WIN",
            "keywords": ["viral", "tips", "shorts"],
        }
    ]
}


def test_metadata_clamps_title_for_shorts() -> None:
    pack = build_platform_pack(
        "YouTube Shorts",
        project_id="p1",
        enabled=True,
        scripts=SCRIPTS,
    )
    assert pack.preset.publish_enabled is False
    assert pack.plan.export_hints.publish_status == "not_published"
    assert pack.plan.export_hints.publish_enabled is False
    max_chars = pack.preset.title_requirements.max_chars
    assert max_chars > 0
    assert len(pack.plan.metadata.title) <= max_chars
    assert pack.plan.metadata.aspect_recommendation == "9:16"


def test_aspect_from_reframe_when_supported() -> None:
    pack = build_platform_pack(
        "LinkedIn",
        project_id="p2",
        enabled=True,
        scripts=SCRIPTS,
        reframe_pack={"plan": {"target_aspect": "1:1"}},
    )
    assert pack.plan.metadata.aspect_recommendation == "1:1"


def test_reddit_subreddit_warning() -> None:
    pack = build_platform_pack(
        "Reddit",
        project_id="p3",
        enabled=True,
        scripts=SCRIPTS,
    )
    assert any("subreddit" in w.lower() for w in pack.plan.metadata.warnings)
    assert pack.plan.export_hints.publish_status == "not_published"


def test_pinterest_prefers_supported_aspect() -> None:
    pack = build_platform_pack(
        "Pinterest",
        project_id="p4",
        enabled=True,
        scripts=SCRIPTS,
        reframe_pack={"plan": {"target_aspect": "16:9"}},
    )
    assert pack.plan.metadata.aspect_recommendation in {"2:3", "9:16"}
    assert any("not in" in w.lower() or "recommending" in w.lower() for w in pack.plan.metadata.warnings)


def test_flag_off_skipped() -> None:
    pack = build_platform_pack("TikTok", project_id="p5", enabled=False)
    assert pack.plan.skipped is True
    assert pack.plan.export_hints.publish_enabled is False
