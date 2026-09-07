"""Moment Detection Agent — unified multi-category highlights → moments.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from agents.base import BaseAgent
from core.errors import MomentDetectionError, StorageError
from core.logging import get_logger
from core.paths import ensure_project_analysis_dir, ensure_project_dir, get_moments_path
from schemas.job import FeatureFlags
from schemas.moments import (
    DetectedMoment,
    MomentDetectionResult,
    MomentsReport,
)
from schemas.project import ProjectMetadata

logger = get_logger(__name__)

AnalyzeFn = Callable[..., list[DetectedMoment]]


class MomentDetectionAgent(BaseAgent):
    """Run specialized analyzers and write analysis/moments.json."""

    name = "moment_detection"

    def __init__(self, analyze_fn: AnalyzeFn | None = None) -> None:
        self._analyze_fn = analyze_fn

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
        viral_moments: dict[str, Any] | None = None,
        **_: Any,
    ) -> MomentDetectionResult:
        meta = self._coerce_project(project)
        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)

        flags = self._coerce_features(features)
        from tools.moments.registry import (
            enabled_categories_from_features,
            run_moment_analyzers,
        )

        enabled = enabled_categories_from_features(flags)

        if not flags.smart_clip_detection:
            report = MomentsReport(
                project_id=project_id,
                enabled_categories=[],
                moments=[],
                provider="disabled",
                notes="smart_clip_detection is off — moment detection skipped.",
                summary_counts={},
            )
            path = self._write_report(project_id, root, report)
            return MomentDetectionResult(
                moments=report,
                moments_path=str(path),
                messages=[f"[{self.name}] Skipped (smart_clip_detection=false)"],
            )

        try:
            if self._analyze_fn is not None:
                moments = self._analyze_fn(
                    enabled=enabled,
                    transcript=transcript,
                    speech_transcript=speech_transcript,
                    scenes=scenes,
                    audio_analysis=audio_analysis,
                    speakers=speakers,
                    analysis=analysis,
                    funny_moments=funny_moments,
                    viral_moments=viral_moments,
                )
            else:
                moments = run_moment_analyzers(
                    enabled=enabled,
                    transcript=transcript,
                    speech_transcript=speech_transcript,
                    scenes=scenes,
                    audio_analysis=audio_analysis,
                    speakers=speakers,
                    analysis=analysis,
                    funny_moments=funny_moments,
                    viral_moments=viral_moments,
                )
        except MomentDetectionError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise MomentDetectionError(f"Moment detection failed: {exc}") from exc

        parsed: list[DetectedMoment] = []
        for m in moments or []:
            if isinstance(m, DetectedMoment):
                parsed.append(m)
            else:
                parsed.append(DetectedMoment.model_validate(m))

        counts: dict[str, int] = {}
        for m in parsed:
            counts[m.category] = counts.get(m.category, 0) + 1

        report = MomentsReport(
            project_id=project_id,
            enabled_categories=list(enabled),
            moments=parsed,
            provider="multi-signal-heuristics",
            notes=(
                "Moments fused from transcript + scenes + audio + speakers. "
                "Not blind single-signal classification."
            ),
            summary_counts=counts,
        )
        path = self._write_report(project_id, root, report)
        messages = [
            f"[{self.name}] Enabled: {', '.join(enabled) or 'none'}",
            f"[{self.name}] Moments: {len(parsed)}",
            f"[{self.name}] Wrote analysis/moments.json",
        ]
        logger.info(
            "MomentDetection ready project_id=%s count=%s",
            project_id,
            len(parsed),
        )
        return MomentDetectionResult(
            moments=report, moments_path=str(path), messages=messages
        )

    def _coerce_project(self, project: ProjectMetadata | dict[str, Any]) -> ProjectMetadata:
        if isinstance(project, ProjectMetadata):
            return project
        try:
            return ProjectMetadata.model_validate(project)
        except Exception as exc:  # noqa: BLE001
            raise MomentDetectionError(f"Invalid project metadata: {exc}") from exc

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
            raise MomentDetectionError(f"Invalid feature flags: {exc}") from exc

    def _write_report(
        self,
        project_id: str,
        root: Path,
        report: MomentsReport,
    ) -> Path:
        path = root / "analysis" / "moments.json"
        try:
            try:
                canonical = get_moments_path(project_id)
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
            raise StorageError(f"Failed to write moments.json: {path}") from exc
        return path.resolve()
