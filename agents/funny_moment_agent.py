"""Funny Moment Agent — dedicated multi-signal humor detection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from agents.base import BaseAgent
from core.errors import FunnyMomentError, StorageError
from core.logging import get_logger
from core.paths import (
    ensure_project_analysis_dir,
    ensure_project_dir,
    get_funny_moments_path,
)
from schemas.funny import FunnyMoment, FunnyMomentResult, FunnyMomentsReport
from schemas.job import FeatureFlags
from schemas.project import ProjectMetadata

logger = get_logger(__name__)

DetectFn = Callable[..., list[FunnyMoment]]


class FunnyMomentAgent(BaseAgent):
    """Write analysis/funny_moments.json; feeds Highlight funny category."""

    name = "funny_moment"

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
        **_: Any,
    ) -> FunnyMomentResult:
        meta = self._coerce_project(project)
        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)
        flags = self._coerce_features(features)

        if not flags.smart_clip_detection or not flags.funny_moments:
            notes = (
                "Funny moment detection skipped "
                f"(smart_clip_detection={flags.smart_clip_detection}, "
                f"funny_moments={flags.funny_moments})."
            )
            report = FunnyMomentsReport(
                project_id=project_id,
                moments=[],
                provider="disabled",
                notes=notes,
                summary={"count": 0.0, "mean_humor_score": 0.0},
            )
            path = self._write_report(project_id, root, report)
            return FunnyMomentResult(
                funny_moments=report,
                funny_moments_path=str(path),
                messages=[f"[{self.name}] {notes}"],
            )

        try:
            from tools.moments.funny_detect import detect_funny_moments

            detect = self._detect_fn or detect_funny_moments
            moments = detect(
                transcript=transcript,
                speech_transcript=speech_transcript,
                scenes=scenes,
                audio_analysis=audio_analysis,
                speakers=speakers,
                analysis=analysis,
            )
        except FunnyMomentError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise FunnyMomentError(f"Funny moment detection failed: {exc}") from exc

        parsed: list[FunnyMoment] = []
        for m in moments or []:
            if isinstance(m, FunnyMoment):
                parsed.append(m)
            else:
                parsed.append(FunnyMoment.model_validate(m))

        mean = (
            sum(m.humor_score for m in parsed) / len(parsed) if parsed else 0.0
        )
        report = FunnyMomentsReport(
            project_id=project_id,
            moments=parsed,
            provider="multi-signal-humor",
            notes=(
                "Laughter is a boost only — humor requires corroborating "
                "transcript/timing/scene/conversational signals."
            ),
            summary={"count": float(len(parsed)), "mean_humor_score": mean},
        )
        path = self._write_report(project_id, root, report)
        messages = [
            f"[{self.name}] Funny moments: {len(parsed)}",
            f"[{self.name}] Mean humor_score: {mean:.2f}",
            f"[{self.name}] Wrote analysis/funny_moments.json",
        ]
        logger.info(
            "FunnyMoment ready project_id=%s count=%s",
            project_id,
            len(parsed),
        )
        return FunnyMomentResult(
            funny_moments=report,
            funny_moments_path=str(path),
            messages=messages,
        )

    def _coerce_project(self, project: ProjectMetadata | dict[str, Any]) -> ProjectMetadata:
        if isinstance(project, ProjectMetadata):
            return project
        try:
            return ProjectMetadata.model_validate(project)
        except Exception as exc:  # noqa: BLE001
            raise FunnyMomentError(f"Invalid project metadata: {exc}") from exc

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
            raise FunnyMomentError(f"Invalid feature flags: {exc}") from exc

    def _write_report(
        self,
        project_id: str,
        root: Path,
        report: FunnyMomentsReport,
    ) -> Path:
        path = root / "analysis" / "funny_moments.json"
        try:
            try:
                canonical = get_funny_moments_path(project_id)
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
            raise StorageError(f"Failed to write funny_moments.json: {path}") from exc
        return path.resolve()
