"""Podcast Agent — package podcast video/audio into short platform clips."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from agents.base import BaseAgent
from core.errors import PodcastAgentError, StorageError
from core.logging import get_logger
from core.paths import (
    ensure_project_analysis_dir,
    ensure_project_dir,
    get_podcast_clips_path,
)
from schemas.job import FeatureFlags, VideoJobConfig
from schemas.podcast import PodcastClip, PodcastClipsReport, PodcastResult
from schemas.project import ProjectMetadata
from tools.podcast.package import (
    detect_source_media,
    is_podcast_video_type,
)

logger = get_logger(__name__)

PackageFn = Callable[..., list[PodcastClip]]


class PodcastAgent(BaseAgent):
    """Write analysis/podcast_clips.json for Shorts/Reels/TikToks/etc."""

    name = "podcast"

    def __init__(self, package_fn: PackageFn | None = None) -> None:
        self._package_fn = package_fn

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
        clips: dict[str, Any] | None = None,
        analysis: dict[str, Any] | None = None,
        source_metadata: dict[str, Any] | None = None,
        upload_path: str | None = None,
        **_: Any,
    ) -> PodcastResult:
        meta = self._coerce_project(project)
        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)
        flags = self._coerce_features(features)
        job_config = self._coerce_config(config)
        enabled = bool(flags.podcast_clips) or is_podcast_video_type(
            job_config.video_type
        )
        media_path = (
            upload_path
            or getattr(meta, "source_path", None)
            or ""
        )
        source_media = detect_source_media(
            upload_path=str(media_path) or None,
            analysis=analysis,
            source_metadata=source_metadata,
        )

        if not enabled:
            notes = (
                "Podcast packaging skipped "
                f"(podcast_clips={flags.podcast_clips}, "
                f"video_type={job_config.video_type!r})."
            )
            report = PodcastClipsReport(
                project_id=project_id,
                clips=[],
                source_media=source_media,  # type: ignore[arg-type]
                provider="disabled",
                notes=notes,
                summary={"count": 0.0, "mean_score": 0.0},
            )
            path = self._write_report(project_id, root, report)
            return PodcastResult(
                podcast_clips=report,
                podcast_clips_path=str(path),
                messages=[f"[{self.name}] {notes}"],
            )

        try:
            from tools.podcast.package import package_podcast_clips

            package = self._package_fn or package_podcast_clips
            from config.settings import get_settings

            target = float(get_settings().podcast_target_duration)
            if not is_podcast_video_type(job_config.video_type):
                target = float(job_config.target_clip_duration or target)

            clips_out = package(
                transcript=transcript,
                speech_transcript=speech_transcript,
                moments=moments,
                funny_moments=funny_moments,
                viral_moments=viral_moments,
                clips=clips,
                analysis=analysis,
                upload_path=str(media_path) or None,
                source_metadata=source_metadata,
                target_duration=target,
            )
        except PodcastAgentError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise PodcastAgentError(f"Podcast packaging failed: {exc}") from exc

        parsed: list[PodcastClip] = []
        for c in clips_out or []:
            if isinstance(c, PodcastClip):
                if c.duration <= 0:
                    c.duration = max(0.0, c.end - c.start)
                parsed.append(c)
            else:
                item = PodcastClip.model_validate(c)
                if item.duration <= 0:
                    item.duration = max(0.0, item.end - item.start)
                parsed.append(item)

        mean_score = (
            sum(c.score for c in parsed) / len(parsed) if parsed else 0.0
        )
        kind_counts: dict[str, float] = {}
        for c in parsed:
            kind_counts[str(c.kind)] = kind_counts.get(str(c.kind), 0.0) + 1.0

        report = PodcastClipsReport(
            project_id=project_id,
            clips=parsed,
            source_media=source_media,  # type: ignore[arg-type]
            provider="podcast-packager",
            notes=(
                "Podcast packages map quotes/funny/viral/lessons into "
                "Shorts/Reels/TikToks/Highlights/Quotes/Clips — plan only, no render."
            ),
            summary={
                "count": float(len(parsed)),
                "mean_score": mean_score,
                **{f"kind_{k}": v for k, v in kind_counts.items()},
            },
        )
        path = self._write_report(project_id, root, report)
        messages = [
            f"[{self.name}] Podcast clips: {len(parsed)}",
            f"[{self.name}] Source media: {report.source_media}",
            f"[{self.name}] Mean score: {mean_score:.2f}",
            f"[{self.name}] Wrote analysis/podcast_clips.json",
        ]
        logger.info(
            "PodcastAgent ready project_id=%s count=%s",
            project_id,
            len(parsed),
        )
        return PodcastResult(
            podcast_clips=report,
            podcast_clips_path=str(path),
            messages=messages,
        )

    def _coerce_project(self, project: ProjectMetadata | dict[str, Any]) -> ProjectMetadata:
        if isinstance(project, ProjectMetadata):
            return project
        try:
            return ProjectMetadata.model_validate(project)
        except Exception as exc:  # noqa: BLE001
            raise PodcastAgentError(f"Invalid project metadata: {exc}") from exc

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
            raise PodcastAgentError(f"Invalid feature flags: {exc}") from exc

    def _coerce_config(
        self, config: VideoJobConfig | dict[str, Any] | None
    ) -> VideoJobConfig:
        if config is None:
            return VideoJobConfig()
        if isinstance(config, VideoJobConfig):
            return config
        try:
            return VideoJobConfig.model_validate(config)
        except Exception as exc:  # noqa: BLE001
            raise PodcastAgentError(f"Invalid job config: {exc}") from exc

    def _write_report(
        self,
        project_id: str,
        root: Path,
        report: PodcastClipsReport,
    ) -> Path:
        path = root / "analysis" / "podcast_clips.json"
        try:
            try:
                canonical = get_podcast_clips_path(project_id)
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
            raise StorageError(f"Failed to write podcast_clips.json: {path}") from exc
        return path.resolve()
