"""Viral Moment Agent — dedicated multi-dimension viral ranking."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from agents.base import BaseAgent
from core.errors import StorageError, ViralMomentError
from core.logging import get_logger
from core.paths import (
    ensure_project_analysis_dir,
    ensure_project_dir,
    get_viral_moments_path,
)
from schemas.job import FeatureFlags
from schemas.project import ProjectMetadata
from schemas.viral import ViralMoment, ViralMomentResult, ViralMomentsReport
from tools.moments.viral_detect import DISCLAIMER, WEIGHTS

logger = get_logger(__name__)

DetectFn = Callable[..., list[ViralMoment]]


class ViralMomentAgent(BaseAgent):
    """Write analysis/viral_moments.json; feeds Highlight viral category."""

    name = "viral_moment"

    def __init__(self, detect_fn: DetectFn | None = None) -> None:
        self._detect_fn = detect_fn

    def run(
        self,
        project: ProjectMetadata | dict[str, Any],
        *,
        project_dir: str | Path | None = None,
        features: FeatureFlags | dict[str, Any] | None = None,
        transcript: dict[str, Any] | None = None,
        speech_transcript: dict[str, Any] | None = None,
        scenes: dict[str, Any] | None = None,
        audio_analysis: dict[str, Any] | None = None,
        speakers: dict[str, Any] | None = None,
        analysis: dict[str, Any] | None = None,
        funny_moments: dict[str, Any] | None = None,
        **_: Any,
    ) -> ViralMomentResult:
        meta = self._coerce_project(project)
        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)
        flags = self._coerce_features(features)

        if not flags.smart_clip_detection or not flags.viral_moments:
            notes = (
                "Viral moment detection skipped "
                f"(smart_clip_detection={flags.smart_clip_detection}, "
                f"viral_moments={flags.viral_moments})."
            )
            report = ViralMomentsReport(
                project_id=project_id,
                moments=[],
                provider="disabled",
                notes=notes,
                summary={"count": 0.0, "mean_final_score": 0.0, "max_final_score": 0.0},
            )
            path = self._write_report(project_id, root, report)
            return ViralMomentResult(
                viral_moments=report,
                viral_moments_path=str(path),
                messages=[f"[{self.name}] {notes}"],
            )

        try:
            from tools.moments.viral_detect import detect_viral_moments

            detect = self._detect_fn or detect_viral_moments
            moments = detect(
                transcript=transcript,
                speech_transcript=speech_transcript,
                scenes=scenes,
                audio_analysis=audio_analysis,
                speakers=speakers,
                analysis=analysis,
                funny_moments=funny_moments,
            )
        except ViralMomentError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ViralMomentError(f"Viral moment detection failed: {exc}") from exc

        parsed: list[ViralMoment] = []
        for m in moments or []:
            if isinstance(m, ViralMoment):
                parsed.append(m)
            else:
                parsed.append(ViralMoment.model_validate(m))

        mean = (
            sum(m.final_score for m in parsed) / len(parsed) if parsed else 0.0
        )
        max_score = max((m.final_score for m in parsed), default=0.0)
        weight_note = ", ".join(f"{k}={v:.2f}" for k, v in WEIGHTS.items())
        report = ViralMomentsReport(
            project_id=project_id,
            moments=parsed,
            provider="multi-signal-viral-rank",
            notes=f"{DISCLAIMER} Weights: {weight_note}.",
            summary={
                "count": float(len(parsed)),
                "mean_final_score": mean,
                "max_final_score": max_score,
            },
        )
        path = self._write_report(project_id, root, report)
        messages = [
            f"[{self.name}] Viral moments ranked: {len(parsed)}",
            f"[{self.name}] Mean final_score: {mean:.2f}",
            f"[{self.name}] Wrote analysis/viral_moments.json",
        ]
        logger.info(
            "ViralMoment ready project_id=%s count=%s",
            project_id,
            len(parsed),
        )
        return ViralMomentResult(
            viral_moments=report,
            viral_moments_path=str(path),
            messages=messages,
        )

    def _coerce_project(self, project: ProjectMetadata | dict[str, Any]) -> ProjectMetadata:
        if isinstance(project, ProjectMetadata):
            return project
        try:
            return ProjectMetadata.model_validate(project)
        except Exception as exc:  # noqa: BLE001
            raise ViralMomentError(f"Invalid project metadata: {exc}") from exc

    def _coerce_features(
        self, features: FeatureFlags | dict[str, Any] | None
    ) -> FeatureFlags:
        if features is None:
            return FeatureFlags()
        if isinstance(features, FeatureFlags):
            return features
        try:
            return FeatureFlags.model_validate(features)
        except Exception as exc:  # noqa: BLE001
            raise ViralMomentError(f"Invalid feature flags: {exc}") from exc

    def _write_report(
        self,
        project_id: str,
        root: Path,
        report: ViralMomentsReport,
    ) -> Path:
        path = root / "analysis" / "viral_moments.json"
        try:
            try:
                canonical = get_viral_moments_path(project_id)
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
            raise StorageError(f"Failed to write viral_moments.json: {path}") from exc
        return path.resolve()
