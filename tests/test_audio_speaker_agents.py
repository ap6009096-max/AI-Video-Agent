"""Tests for Audio and Speaker analysis agents."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.audio_analysis_agent import AudioAnalysisAgent
from agents.speaker_analysis_agent import SpeakerAnalysisAgent
from config.settings import get_settings
from schemas.audio_speakers import (
    ConversationalStructure,
    ScoredSpan,
    SpeakerTurn,
)
from schemas.base import JobStatus
from schemas.job import SourceType
from schemas.project import ProjectMetadata


def test_agents_write_json_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()

    project_dir = tmp_path / "outputs" / "projects" / "as-1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="as-1",
        source_type=SourceType.SCRIPT,
        raw_text="Hello?",
        status=JobStatus.RUNNING,
    )

    def _fake_audio(**_):
        return {
            "silence_spans": [],
            "pause_spans": [
                ScoredSpan(
                    start=1.0,
                    end=2.0,
                    score=0.5,
                    label="pause",
                    evidence_tags=["clip_boundary"],
                )
            ],
            "volume_events": [],
            "intensity_spans": [],
            "laughter_candidates": [],
            "excitement_candidates": [],
            "question_spans": [
                ScoredSpan(
                    start=0.0,
                    end=1.0,
                    score=0.7,
                    label="question",
                    evidence_tags=["clip_boundary"],
                )
            ],
            "reaction_spans": [],
            "summary_scores": {
                "silence_ratio": 0.0,
                "speech_intensity": 0.4,
                "volume_dynamics": 0.0,
                "laughter": 0.0,
                "excitement": 0.0,
                "pause_density": 0.2,
                "question_density": 1.0,
                "reaction_density": 0.0,
            },
            "notes": "",
        }

    def _fake_speakers(**_):
        return {
            "turns": [
                SpeakerTurn(id=0, start=0.0, end=1.0, text_excerpt="Hello?", change_score=0.0)
            ],
            "speaker_change_candidates": [],
            "conversational_structure": ConversationalStructure(turn_taking=0.0),
            "summary_scores": {"speaker_change_rate": 0.0, "turn_count": 1.0},
            "notes": "Speaker-independent turn heuristics — not true diarization or voice IDs.",
        }

    audio_result = AudioAnalysisAgent(analyze_fn=_fake_audio).run(
        project, project_dir=project_dir, transcript={"sentences": []}
    )
    audio_path = Path(audio_result.audio_analysis_path)
    assert audio_path.is_file()
    audio_data = json.loads(audio_path.read_text(encoding="utf-8"))
    assert "summary_scores" in audio_data
    assert audio_data["summary_scores"]["question_density"] == 1.0
    assert audio_data["question_spans"]

    speaker_result = SpeakerAnalysisAgent(analyze_fn=_fake_speakers).run(
        project,
        project_dir=project_dir,
        audio_analysis=audio_data,
    )
    speakers_path = Path(speaker_result.speakers_path)
    assert speakers_path.is_file()
    speakers_data = json.loads(speakers_path.read_text(encoding="utf-8"))
    assert speakers_data["turns"]
    assert "speaker_change_rate" in speakers_data["summary_scores"]
    assert "diarization" in speakers_data["notes"].lower()

    get_settings.cache_clear()


def test_transcript_only_audio_agent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "as-script"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="as-script",
        source_type=SourceType.SCRIPT,
        raw_text="Why now? haha",
    )
    result = AudioAnalysisAgent().run(
        project,
        project_dir=project_dir,
        transcript={
            "sentences": [
                {"start_seconds": 0.0, "end_seconds": 1.0, "text": "Why now?"},
                {"start_seconds": 2.0, "end_seconds": 2.5, "text": "haha"},
            ]
        },
    )
    assert result.audio_analysis.provider == "transcript-only"
    assert Path(result.audio_analysis_path).is_file()
    get_settings.cache_clear()
