"""Tests for the Text/Script Agent with mocked Gemini analysis."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.text_agent import TextAgent
from config.settings import get_settings
from core.errors import TextAgentError
from schemas.base import JobStatus
from schemas.job import SourceType
from schemas.project import ProjectMetadata
from schemas.transcript import GeminiHook, GeminiImportantStatement, GeminiScriptAnalysis


def _fake_analysis(cleaned_text, sentences, sections) -> GeminiScriptAnalysis:
    return GeminiScriptAnalysis(
        language="English",
        topics=["productivity", "habits"],
        section_titles=[f"Part {i + 1}" for i in range(len(sections))],
        hooks=[GeminiHook(sentence_index=0, reason="Strong opener", score=0.9)],
        important_statements=[
            GeminiImportantStatement(sentence_index=0, reason="Core claim")
        ],
        clip_boundaries=[],
    )


def test_text_agent_writes_transcript_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()

    project_dir = tmp_path / "outputs" / "projects" / "script-1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="script-1",
        source_type=SourceType.SCRIPT,
        raw_text="Hooks matter. This is an important statement about habits.",
        status=JobStatus.RUNNING,
    )

    result = TextAgent(analyze_fn=_fake_analysis).run(project, project_dir=project_dir)

    assert result.transcript.language == "English"
    assert "productivity" in result.transcript.topics
    assert result.transcript.sentences
    assert result.transcript.hooks
    assert result.transcript.hooks[0].sentence_id == "s0"
    assert result.transcript.provider == "gemini"

    path = Path(result.transcript_path)
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["project_id"] == "script-1"
    assert data["cleaned_text"]
    assert data["topics"]
    assert data["hooks"]
    assert (Path(result.source_dir) / "source_metadata.json").is_file()

    get_settings.cache_clear()


def test_text_agent_rejects_empty_script(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()

    project = ProjectMetadata(
        project_id="empty",
        source_type=SourceType.SCRIPT,
        raw_text="   ",
    )
    with pytest.raises(TextAgentError, match="missing script|empty"):
        TextAgent(analyze_fn=_fake_analysis).run(project, project_dir=tmp_path / "p")
    get_settings.cache_clear()
