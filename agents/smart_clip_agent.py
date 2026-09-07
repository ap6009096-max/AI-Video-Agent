"""Smart Clip Selection Agent — boundary-aware clips → clips.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from agents.base import BaseAgent
from core.errors import SmartClipError, StorageError
from core.logging import get_logger
from core.paths import (
    ensure_project_analysis_dir,
    ensure_project_dir,
    get_clips_path,
)
from schemas.clips import ClipCandidate, ClipsReport, SmartClipResult
from schemas.job import FeatureFlags, VideoJobConfig
from schemas.project import ProjectMetadata

logger = get_logger(__name__)

SelectFn = Callable[..., list[ClipCandidate]]


class SmartClipAgent(BaseAgent):
    """Write analysis/clips.json from natural boundaries and ranked moments."""

    name = "smart_clip"

    def __init__(
        self,
        select_fn: SelectFn | None = None,
        select_multi_fn: SelectFn | None = None,
    ) -> None:
        self._select_fn = select_fn
        self._select_multi_fn = select_multi_fn

    def run(
        self,
        project: ProjectMetadata | dict[str, Any],
        *,
        project_dir: str | Path | None = None,
        features: FeatureFlags | dict[str, Any] | None = None,
        config: VideoJobConfig | dict[str, Any] | None = None,
        transcript: dict[str, Any] | None = None,
        speech_transcript: dict[str, Any] | None = None,
        scenes: dict[str, Any] | None = None,
        audio_analysis: dict[str, Any] | None = None,
        speakers: dict[str, Any] | None = None,
        moments: dict[str, Any] | None = None,
        funny_moments: dict[str, Any] | None = None,
        viral_moments: dict[str, Any] | None = None,
        analysis: dict[str, Any] | None = None,
        documentary_pack: dict[str, Any] | None = None,
        director_pack: dict[str, Any] | None = None,
        **_: Any,
    ) -> SmartClipResult:
        meta = self._coerce_project(project)
        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)
        flags = self._coerce_features(features)
        job_config = self._coerce_config(config)
        target = float(job_config.target_clip_duration)
        short_durations = [
            int(d) for d in (job_config.short_durations or [10, 40, 90])
        ]
        multi = bool(getattr(flags, "multi_shorts_export", False))

        if not flags.smart_clip_detection:
            notes = "Smart clip selection skipped (smart_clip_detection=false)."
            report = ClipsReport(
                project_id=project_id,
                clips=[],
                target_duration=target,
                short_durations=short_durations if multi else [],
                multi_shorts=multi,
                provider="disabled",
                notes=notes,
                summary={"count": 0.0, "mean_score": 0.0, "mean_duration": 0.0},
            )
            path = self._write_report(project_id, root, report)
            return SmartClipResult(
                clips=report,
                clips_path=str(path),
                messages=[f"[{self.name}] {notes}"],
            )

        try:
            from tools.clips.select import (
                select_multi_duration_clips,
                select_smart_clips,
            )

            if multi and self._select_fn is None:
                select_multi = self._select_multi_fn or select_multi_duration_clips
                clips = select_multi(
                    transcript=transcript,
                    speech_transcript=speech_transcript,
                    scenes=scenes,
                    audio_analysis=audio_analysis,
                    speakers=speakers,
                    moments=moments,
                    funny_moments=funny_moments,
                    viral_moments=viral_moments,
                    analysis=analysis,
                    documentary_pack=(
                        documentary_pack if isinstance(documentary_pack, dict) else None
                    ),
                    director_pack=(
                        director_pack if isinstance(director_pack, dict) else None
                    ),
                    short_durations=short_durations,
                )
                provider = "smart-clip-multi-duration"
            else:
                select = self._select_fn or select_smart_clips
                clips = select(
                    transcript=transcript,
                    speech_transcript=speech_transcript,
                    scenes=scenes,
                    audio_analysis=audio_analysis,
                    speakers=speakers,
                    moments=moments,
                    funny_moments=funny_moments,
                    viral_moments=viral_moments,
                    analysis=analysis,
                    target_duration=target,
                )
                provider = "smart-clip-boundaries"
        except SmartClipError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise SmartClipError(f"Smart clip selection failed: {exc}") from exc

        parsed: list[ClipCandidate] = []
        for c in clips or []:
            if isinstance(c, ClipCandidate):
                if c.duration <= 0:
                    c.duration = max(0.0, c.end - c.start)
                if c.target_duration <= 0:
                    c.target_duration = target
                parsed.append(c)
            else:
                item = ClipCandidate.model_validate(c)
                if item.duration <= 0:
                    item.duration = max(0.0, item.end - item.start)
                if item.target_duration <= 0:
                    item.target_duration = target
                parsed.append(item)

        mean_score = (
            sum(c.score for c in parsed) / len(parsed) if parsed else 0.0
        )
        mean_dur = (
            sum(c.duration for c in parsed) / len(parsed) if parsed else 0.0
        )
        notes = (
            "Multi-duration Shorts clips from analysis boundaries "
            f"(durations={short_durations})."
            if multi
            else (
                "Clips snapped to transcript/scene/speaker/audio boundaries — "
                "not fixed time chunks. Target duration is a ranking preference."
            )
        )
        report = ClipsReport(
            project_id=project_id,
            clips=parsed,
            target_duration=target,
            short_durations=short_durations if multi else [],
            multi_shorts=multi,
            provider=provider,
            notes=notes,
            summary={
                "count": float(len(parsed)),
                "mean_score": mean_score,
                "mean_duration": mean_dur,
            },
        )
        path = self._write_report(project_id, root, report)
        messages = [
            f"[{self.name}] Selected clips: {len(parsed)}",
            (
                f"[{self.name}] Multi Shorts durations: {short_durations}"
                if multi
                else f"[{self.name}] Target duration: {target:.0f}s"
            ),
            f"[{self.name}] Mean score: {mean_score:.2f}",
            f"[{self.name}] Wrote analysis/clips.json",
        ]
        logger.info(
            "SmartClip ready project_id=%s count=%s multi=%s",
            project_id,
            len(parsed),
            multi,
        )
        return SmartClipResult(
            clips=report,
            clips_path=str(path),
            messages=messages,
        )

    def _coerce_project(self, project: ProjectMetadata | dict[str, Any]) -> ProjectMetadata:
        if isinstance(project, ProjectMetadata):
            return project
        try:
            return ProjectMetadata.model_validate(project)
        except Exception as exc:  # noqa: BLE001
            raise SmartClipError(f"Invalid project metadata: {exc}") from exc

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
            raise SmartClipError(f"Invalid feature flags: {exc}") from exc

    def _coerce_config(
        self, config: VideoJobConfig | dict[str, Any] | None
    ) -> VideoJobConfig:
        if config is None:
            from config.settings import get_settings

            default = get_settings().clip_target_duration
            if default not in (15, 30, 45, 60, 90):
                default = 30
            return VideoJobConfig(target_clip_duration=default)  # type: ignore[arg-type]
        if isinstance(config, VideoJobConfig):
            return config
        try:
            return VideoJobConfig.model_validate(config)
        except Exception as exc:  # noqa: BLE001
            raise SmartClipError(f"Invalid job config: {exc}") from exc

    def _write_report(
        self,
        project_id: str,
        root: Path,
        report: ClipsReport,
    ) -> Path:
        path = root / "analysis" / "clips.json"
        try:
            try:
                canonical = get_clips_path(project_id)
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
            raise StorageError(f"Failed to write clips.json: {path}") from exc
        return path.resolve()
