"""Audio Analysis Agent — scored silence/intensity/laughter/etc. evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from agents.base import BaseAgent
from core.errors import AudioAnalysisError, StorageError
from core.logging import get_logger
from core.paths import (
    ensure_project_analysis_dir,
    ensure_project_dir,
    get_audio_analysis_path,
)
from schemas.audio_speakers import AudioAnalysisReport, AudioAnalysisResult, ScoredSpan
from schemas.project import ProjectMetadata

logger = get_logger(__name__)

AnalyzeFn = Callable[..., dict[str, Any]]


class AudioAnalysisAgent(BaseAgent):
    """Produce audio_analysis.json as supporting evidence for moment agents."""

    name = "audio_analysis"

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
        **_: Any,
    ) -> AudioAnalysisResult:
        meta = self._coerce_project(project)
        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)
        media_path = self._resolve_media_path(meta, source_metadata)

        try:
            from tools.audio.signal_analysis import analyze_audio_signals

            analyze = self._analyze_fn or analyze_audio_signals
            raw = analyze(
                media_path=media_path,
                analysis=analysis,
                speech_transcript=speech_transcript,
                transcript=transcript,
            )
        except AudioAnalysisError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise AudioAnalysisError(f"Audio analysis failed: {exc}") from exc

        provider = "ffmpeg-transcript"
        notes = str(raw.get("notes") or "")
        if not media_path:
            provider = "transcript-only"
            notes = notes or (
                "Transcript-only audio analysis: no local media. "
                "Silence/volume from analysis used when present."
            )

        report = AudioAnalysisReport(
            project_id=project_id,
            media_path=str(Path(media_path).resolve()) if media_path else "",
            provider=provider,
            notes=notes,
            silence_spans=_as_spans(raw.get("silence_spans")),
            pause_spans=_as_spans(raw.get("pause_spans")),
            volume_events=_as_spans(raw.get("volume_events")),
            intensity_spans=_as_spans(raw.get("intensity_spans")),
            laughter_candidates=_as_spans(raw.get("laughter_candidates")),
            excitement_candidates=_as_spans(raw.get("excitement_candidates")),
            question_spans=_as_spans(raw.get("question_spans")),
            reaction_spans=_as_spans(raw.get("reaction_spans")),
            summary_scores={
                str(k): float(v) for k, v in (raw.get("summary_scores") or {}).items()
            },
        )
        path = self._write_report(project_id, root, report)
        messages = [
            f"[{self.name}] Provider: {provider}",
            f"[{self.name}] Questions: {len(report.question_spans)}, "
            f"laughter: {len(report.laughter_candidates)}",
            f"[{self.name}] Wrote analysis/audio_analysis.json",
        ]
        logger.info(
            "AudioAnalysis ready project_id=%s provider=%s",
            project_id,
            provider,
        )
        return AudioAnalysisResult(
            audio_analysis=report,
            audio_analysis_path=str(path),
            messages=messages,
        )

    def _coerce_project(self, project: ProjectMetadata | dict[str, Any]) -> ProjectMetadata:
        if isinstance(project, ProjectMetadata):
            return project
        try:
            return ProjectMetadata.model_validate(project)
        except Exception as exc:  # noqa: BLE001
            raise AudioAnalysisError(f"Invalid project metadata: {exc}") from exc

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
        report: AudioAnalysisReport,
    ) -> Path:
        path = root / "analysis" / "audio_analysis.json"
        try:
            try:
                canonical = get_audio_analysis_path(project_id)
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
            raise StorageError(f"Failed to write audio_analysis.json: {path}") from exc
        return path.resolve()


def _as_spans(items: Any) -> list[ScoredSpan]:
    out: list[ScoredSpan] = []
    for item in items or []:
        if isinstance(item, ScoredSpan):
            out.append(item)
        else:
            out.append(ScoredSpan.model_validate(item))
    return out
