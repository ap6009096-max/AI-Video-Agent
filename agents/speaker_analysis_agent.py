"""Speaker Analysis Agent — turn candidates + conversational structure."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from agents.base import BaseAgent
from core.errors import SpeakerAnalysisError, StorageError
from core.logging import get_logger
from core.paths import ensure_project_analysis_dir, ensure_project_dir, get_speakers_path
from schemas.audio_speakers import (
    ConversationalStructure,
    ScoredSpan,
    SpeakerAnalysisReport,
    SpeakerAnalysisResult,
    SpeakerTurn,
)
from schemas.project import ProjectMetadata

logger = get_logger(__name__)

AnalyzeFn = Callable[..., dict[str, Any]]


class SpeakerAnalysisAgent(BaseAgent):
    """Produce speakers.json (heuristics, not diarization)."""

    name = "speaker_analysis"

    def __init__(self, analyze_fn: AnalyzeFn | None = None) -> None:
        self._analyze_fn = analyze_fn

    def run(
        self,
        project: ProjectMetadata | dict[str, Any],
        *,
        project_dir: str | Path | None = None,
        source_metadata: dict[str, Any] | None = None,
        analysis: dict[str, Any] | None = None,
        speech_transcript: dict[str, Any] | None = None,
        transcript: dict[str, Any] | None = None,
        audio_analysis: dict[str, Any] | None = None,
        scenes: dict[str, Any] | None = None,
        **_: Any,
    ) -> SpeakerAnalysisResult:
        meta = self._coerce_project(project)
        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)
        media_path = self._resolve_media_path(meta, source_metadata)

        try:
            from tools.audio.speaker_analysis import analyze_speakers

            analyze = self._analyze_fn or analyze_speakers
            raw = analyze(
                speech_transcript=speech_transcript,
                transcript=transcript,
                audio_analysis=audio_analysis,
                scenes=scenes,
                analysis=analysis,
            )
        except SpeakerAnalysisError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise SpeakerAnalysisError(f"Speaker analysis failed: {exc}") from exc

        turns = []
        for t in raw.get("turns") or []:
            if isinstance(t, SpeakerTurn):
                turns.append(t)
            else:
                turns.append(SpeakerTurn.model_validate(t))

        changes = []
        for c in raw.get("speaker_change_candidates") or []:
            if isinstance(c, ScoredSpan):
                changes.append(c)
            else:
                changes.append(ScoredSpan.model_validate(c))

        structure_raw = raw.get("conversational_structure") or {}
        if isinstance(structure_raw, ConversationalStructure):
            structure = structure_raw
        else:
            structure = ConversationalStructure.model_validate(structure_raw)

        notes = str(raw.get("notes") or "")
        provider = "transcript-heuristics"
        if not media_path:
            provider = "transcript-only"

        report = SpeakerAnalysisReport(
            project_id=project_id,
            media_path=str(Path(media_path).resolve()) if media_path else "",
            provider=provider,
            notes=notes
            or "Speaker-independent turn heuristics — not true diarization or voice IDs.",
            turns=turns,
            speaker_change_candidates=changes,
            conversational_structure=structure,
            summary_scores={
                str(k): float(v) for k, v in (raw.get("summary_scores") or {}).items()
            },
        )
        path = self._write_report(project_id, root, report)
        messages = [
            f"[{self.name}] Turns: {len(turns)}, changes: {len(changes)}",
            f"[{self.name}] Wrote analysis/speakers.json",
        ]
        logger.info(
            "SpeakerAnalysis ready project_id=%s turns=%s",
            project_id,
            len(turns),
        )
        return SpeakerAnalysisResult(
            speakers=report, speakers_path=str(path), messages=messages
        )

    def _coerce_project(self, project: ProjectMetadata | dict[str, Any]) -> ProjectMetadata:
        if isinstance(project, ProjectMetadata):
            return project
        try:
            return ProjectMetadata.model_validate(project)
        except Exception as exc:  # noqa: BLE001
            raise SpeakerAnalysisError(f"Invalid project metadata: {exc}") from exc

    def _resolve_media_path(
        self,
        meta: ProjectMetadata,
        source_metadata: dict[str, Any] | None,
    ) -> str | None:
        candidates: list[str] = []
        if meta.source_path:
            candidates.append(meta.source_path)
        if source_metadata and source_metadata.get("local_media_path"):
            candidates.append(str(source_metadata["local_media_path"]))
        for path in candidates:
            if path and Path(path).is_file():
                return path
        return None

    def _write_report(
        self,
        project_id: str,
        root: Path,
        report: SpeakerAnalysisReport,
    ) -> Path:
        path = root / "analysis" / "speakers.json"
        try:
            try:
                canonical = get_speakers_path(project_id)
                if canonical.parent.parent == root.resolve():
                    path = canonical
            except Exception:  # noqa: BLE001
                pass
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                ensure_project_analysis_dir(project_id)
            except Exception:  # noqa: BLE001
                pass
            path.write_text(
                json.dumps(report.model_dump(mode="json"), indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            raise StorageError(f"Failed to write speakers.json: {path}") from exc
        return path.resolve()
