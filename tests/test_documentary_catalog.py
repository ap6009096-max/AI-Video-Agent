"""Tests for documentary catalog."""

from __future__ import annotations

from schemas.documentary import DocumentaryChapter, GeminiDocumentaryBatch
from schemas.job import VideoJobConfig
from tools.documentary.catalog import (
    build_documentary_pack,
    clear_documentary_cache,
)


def test_flag_off_skips() -> None:
    clear_documentary_cache()
    pack = build_documentary_pack(enabled=False)
    assert pack.plan.skipped is True
    assert pack.plan.chapters == []
    assert pack.plan.provider == "none"


def test_heuristic_has_arc_and_plans() -> None:
    clear_documentary_cache()
    pack = build_documentary_pack(
        enabled=True,
        config=VideoJobConfig(visual_style="Cinematic", video_type="Documentary"),
        script_pack={
            "primary": {
                "title": "River Truths",
                "hook": "What hides in the current?",
                "script": "Flows rose 40%. Experts warn of change. Tip: watch upstream.",
            }
        },
        storyboard_pack={
            "plan": {
                "skipped": False,
                "shots": [
                    {"scene": 1, "visual": "River open", "voiceover": "The river"},
                    {"scene": 2, "visual": "Gauge", "voiceover": "Numbers rise"},
                    {"scene": 3, "visual": "Town", "voiceover": "People adapt"},
                ],
            }
        },
        character_pack={
            "plan": {
                "skipped": False,
                "characters": [{"name": "Dr. Lee", "role_type": "human"}],
            }
        },
        analyze_fn=None,
    )
    assert pack.plan.skipped is False
    assert pack.plan.introduction
    assert pack.plan.conclusion
    assert len(pack.plan.chapters) >= 1
    assert pack.plan.research_structure
    assert pack.plan.evidence_structure
    assert pack.plan.narration_plan
    assert pack.plan.interview_plan
    assert pack.plan.timeline_plan
    assert pack.plan.documentary_plan


def test_inject_analyze_fn() -> None:
    clear_documentary_cache()

    def _fake(**_: object) -> GeminiDocumentaryBatch:
        return GeminiDocumentaryBatch(
            introduction="Cold open on the claim.",
            chapters=[
                DocumentaryChapter(
                    title="Origins",
                    summary="Where it began",
                    research="Archive dig",
                    evidence="Letter dated 1902",
                    narration="It started quietly.",
                    interview="Ask the historian",
                    timeline="Act 1",
                    scene=1,
                )
            ],
            conclusion="What remains unanswered.",
            research_structure=["Archive dig"],
            evidence_structure=["Letter dated 1902"],
            narration_plan=["It started quietly."],
            interview_plan=["Ask the historian"],
            timeline_plan=["Act 1"],
        )

    pack = build_documentary_pack(enabled=True, analyze_fn=_fake)
    assert pack.plan.provider == "gemini"
    assert pack.plan.chapters[0].title == "Origins"
    assert "intro:" in pack.plan.documentary_plan[0]
