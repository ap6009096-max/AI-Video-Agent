"""Tests for research report builder."""

from __future__ import annotations

from tools.research.build import (
    build_research_report,
    format_research_grounding_block,
    should_enable_research,
)
from schemas.job import SourceType
from schemas.research import ResearchClaim, ResearchReport, ResearchSource


def test_should_enable_research_gate() -> None:
    assert should_enable_research(research_flag=True, source_type="upload")
    assert should_enable_research(research_flag=False, source_type=SourceType.SCRIPT)
    assert not should_enable_research(research_flag=False, source_type="upload")


def test_build_from_script_and_transcript() -> None:
    transcript = {
        "cleaned_text": "Sleep is essential. Deep sleep restores memory.",
        "topics": ["Sleep science"],
        "sections": [
            {
                "id": "s1",
                "title": "Why sleep matters",
                "summary": "Sleep is essential for recovery.",
            }
        ],
        "important_statements": [
            {"text": "Sleep is essential for memory consolidation.", "score": 0.9}
        ],
        "hooks": [{"text": "Most people ignore deep sleep.", "score": 0.7}],
        "sentences": [
            {
                "id": "0",
                "text": "Sleep is essential for memory consolidation overnight.",
                "start_seconds": 0.0,
                "end_seconds": 4.0,
            }
        ],
    }
    report = build_research_report(
        project_id="r1",
        raw_text="Sleep is essential. Deep sleep restores memory.",
        transcript=transcript,
        enrich_fn=lambda **_k: None,
    )
    assert report.skipped is False
    assert report.topic
    assert report.sources
    assert report.claims
    assert report.outline
    assert report.summary
    source_ids = {s.id for s in report.sources}
    for claim in report.claims:
        assert claim.source_ids
        assert all(sid in source_ids for sid in claim.source_ids)


def test_rejects_unsourced_claims_via_filter() -> None:
    report = build_research_report(
        project_id="r2",
        raw_text="A short claim about climate is important.",
        enrich_fn=lambda **_k: None,
    )
    for claim in report.claims:
        assert claim.source_ids


def test_empty_corpus_still_has_structure() -> None:
    report = build_research_report(
        project_id="r3",
        enrich_fn=lambda **_k: None,
    )
    assert report.claims == []
    assert report.summary
    assert report.provider == "research-builder"


def test_skipped_report() -> None:
    report = build_research_report(project_id="r4", skipped=True, notes="off")
    assert report.skipped is True
    assert report.claims == []
    assert report.provider == "disabled"


def test_format_research_grounding_block() -> None:
    report = ResearchReport(
        project_id="r5",
        topic="Sleep",
        summary="Sleep matters.",
        sources=[
            ResearchSource(
                id="src:user_script",
                kind="user_script",
                title="User script",
                excerpt="Sleep is essential.",
            )
        ],
        claims=[
            ResearchClaim(
                id="claim:0",
                text="Sleep is essential.",
                source_ids=["src:user_script"],
                confidence=0.8,
            )
        ],
    )
    block = format_research_grounding_block(report)
    assert "Sleep" in block
    assert "Sleep is essential" in block
    assert format_research_grounding_block({"skipped": True}) == ""
