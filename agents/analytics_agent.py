"""Analytics Agent — predict engagement/retention/shareability (Gemini or heuristic)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agents.base import BaseAgent
from core.errors import AnalyticsAgentError, StorageError
from core.logging import get_logger
from core.paths import (
    ensure_project_analysis_dir,
    ensure_project_dir,
    get_analytics_plan_path,
)
from schemas.analytics import AnalyticsPack, AnalyticsResult
from schemas.job import FeatureFlags, VideoJobConfig
from schemas.project import ProjectMetadata
from tools.analytics.catalog import AnalyzeFn, build_analytics_pack

logger = get_logger(__name__)


class AnalyticsAgent(BaseAgent):
    """Write analysis/analytics_plan.json with engagement/retention/shareability."""

    name = "analytics"

    def run(
        self,
        project: ProjectMetadata | dict[str, Any],
        *,
        project_dir: str | Path | None = None,
        config: VideoJobConfig | dict[str, Any] | None = None,
        features: FeatureFlags | dict[str, Any] | None = None,
        script_pack: dict[str, Any] | None = None,
        platform_pack: dict[str, Any] | None = None,
        seo_pack: dict[str, Any] | None = None,
        trend_pack: dict[str, Any] | None = None,
        repurpose_pack: dict[str, Any] | None = None,
        thumbnail_pack: dict[str, Any] | None = None,
        viral_pack: dict[str, Any] | None = None,
        analyze_fn: AnalyzeFn | None = None,
        **_: Any,
    ) -> AnalyticsResult:
        meta = self._coerce_project(project)
        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)
        job_config = self._coerce_config(config)
        flags = self._coerce_features(features)

        platform_label = (job_config.platform or "").strip() or "YouTube"

        try:
            pack = build_analytics_pack(
                platform_label,
                enabled=bool(flags.analytics),
                config=job_config,
                script_pack=script_pack if isinstance(script_pack, dict) else None,
                platform_pack=platform_pack if isinstance(platform_pack, dict) else None,
                seo_pack=seo_pack if isinstance(seo_pack, dict) else None,
                trend_pack=trend_pack if isinstance(trend_pack, dict) else None,
                repurpose_pack=(
                    repurpose_pack if isinstance(repurpose_pack, dict) else None
                ),
                thumbnail_pack=(
                    thumbnail_pack if isinstance(thumbnail_pack, dict) else None
                ),
                viral_pack=viral_pack if isinstance(viral_pack, dict) else None,
                analyze_fn=analyze_fn,
            )
        except Exception as exc:  # noqa: BLE001
            raise AnalyticsAgentError(f"Analytics planning failed: {exc}") from exc

        path = self._write_pack(project_id, root, pack)
        public = {
            "engagement_score": pack.plan.engagement_score,
            "retention_score": pack.plan.retention_score,
            "shareability_score": pack.plan.shareability_score,
        }
        messages = [
            f"[{self.name}] {pack.notes}",
            f"[{self.name}] Output: {json.dumps(public, ensure_ascii=False)}",
            f"[{self.name}] Wrote analysis/analytics_plan.json",
        ]
        logger.info(
            "AnalyticsAgent ready project_id=%s platform=%s engagement=%s skipped=%s",
            project_id,
            pack.plan.platform,
            pack.plan.engagement_score,
            pack.plan.skipped,
        )
        return AnalyticsResult(
            analytics_pack=pack, analytics_path=str(path), messages=messages
        )

    def _coerce_project(
        self, project: ProjectMetadata | dict[str, Any]
    ) -> ProjectMetadata:
        if isinstance(project, ProjectMetadata):
            return project
        try:
            return ProjectMetadata.model_validate(project)
        except Exception as exc:  # noqa: BLE001
            raise AnalyticsAgentError(f"Invalid project metadata: {exc}") from exc

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
            raise AnalyticsAgentError(f"Invalid job config: {exc}") from exc

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
            raise AnalyticsAgentError(f"Invalid feature flags: {exc}") from exc

    def _write_pack(
        self,
        project_id: str,
        root: Path,
        pack: AnalyticsPack,
    ) -> Path:
        path = root / "analysis" / "analytics_plan.json"
        try:
            try:
                canonical = get_analytics_plan_path(project_id)
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
                json.dumps(pack.model_dump(mode="json"), indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            raise StorageError(f"Failed to write analytics_plan.json: {path}") from exc
        return path.resolve()
