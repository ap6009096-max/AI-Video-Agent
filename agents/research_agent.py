"""Research Agent — topic analysis, sourced claims, outline, summary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from agents.base import BaseAgent
from core.errors import ResearchAgentError, StorageError
from core.logging import get_logger
from core.paths import (
    ensure_project_analysis_dir,
    ensure_project_dir,
    get_research_report_path,
)
from schemas.job import FeatureFlags, SourceType, VideoJobConfig
from schemas.project import ProjectMetadata
from schemas.research import ResearchReport, ResearchResult
from tools.research.build import (
    build_research_report,
    should_enable_research,
)

logger = get_logger(__name__)

BuildFn = Callable[..., ResearchReport]


class ResearchAgent(BaseAgent):
    """Write analysis/research_report.json from project corpus."""

    name = "research"

    def __init__(self, build_fn: BuildFn | None = None) -> None:
        self._build_fn = build_fn

    def run(
        self,
        project: ProjectMetadata | dict[str, Any],
        *,
        project_dir: str | Path | None = None,
        features: FeatureFlags | dict[str, Any] | None = None,
        config: VideoJobConfig | dict[str, Any] | None = None,
        transcript: dict[str, Any] | None = None,
        speech_transcript: dict[str, Any] | None = None,
        analysis: dict[str, Any] | None = None,
        source_metadata: dict[str, Any] | None = None,
        source_type: str | SourceType | None = None,
        youtube_url: str | None = None,
        **_: Any,
    ) -> ResearchResult:
        meta = self._coerce_project(project)
        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)
        flags = self._coerce_features(features)
        job_config = self._coerce_config(config)
        st = source_type if source_type is not None else meta.source_type
        enabled = should_enable_research(
            research_flag=bool(flags.research),
            source_type=st,
        )
        yt = (
            youtube_url
            or getattr(meta, "youtube_url", None)
            or ""
        )
        raw_text = getattr(meta, "raw_text", None) or ""

        build = self._build_fn or build_research_report

        if not enabled:
            notes = (
                "Research skipped "
                f"(research={flags.research}, source_type={st!r})."
            )
            report = build(
                project_id=project_id,
                skipped=True,
                notes=notes,
            )
            path = self._write_report(project_id, root, report)
            return ResearchResult(
                research_report=report,
                research_report_path=str(path),
                messages=[f"[{self.name}] {notes}"],
            )

        try:
            report = build(
                project_id=project_id,
                raw_text=raw_text,
                transcript=transcript,
                speech_transcript=speech_transcript,
                analysis=analysis,
                source_metadata=source_metadata,
                youtube_url=str(yt) or None,
                skipped=False,
            )
        except ResearchAgentError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ResearchAgentError(f"Research build failed: {exc}") from exc

        # Hard guarantee: drop unsourced claims
        report.claims = [c for c in report.claims if c.source_ids]
        path = self._write_report(project_id, root, report)
        messages = [
            f"[{self.name}] Topic: {report.topic or '(none)'}",
            f"[{self.name}] Sources: {len(report.sources)} claims: {len(report.claims)}",
            f"[{self.name}] Outline sections: {len(report.outline)}",
            f"[{self.name}] Wrote analysis/research_report.json",
        ]
        logger.info(
            "ResearchAgent ready project_id=%s claims=%s sources=%s",
            project_id,
            len(report.claims),
            len(report.sources),
        )
        return ResearchResult(
            research_report=report,
            research_report_path=str(path),
            messages=messages,
        )

    def _coerce_project(self, project: ProjectMetadata | dict[str, Any]) -> ProjectMetadata:
        if isinstance(project, ProjectMetadata):
            return project
        try:
            return ProjectMetadata.model_validate(project)
        except Exception as exc:  # noqa: BLE001
            raise ResearchAgentError(f"Invalid project metadata: {exc}") from exc

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
            raise ResearchAgentError(f"Invalid feature flags: {exc}") from exc

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
            raise ResearchAgentError(f"Invalid job config: {exc}") from exc

    def _write_report(
        self, project_id: str, root: Path, report: ResearchReport
    ) -> Path:
        ensure_project_analysis_dir(project_id)
        path = root / "analysis" / "research_report.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            canonical = get_research_report_path(project_id)
            if canonical.resolve() != path.resolve():
                # Prefer project_dir path when tests use custom OUTPUT_DIR roots
                pass
            path.write_text(
                json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            raise StorageError(f"Failed to write research_report.json: {path}") from exc
        return path
