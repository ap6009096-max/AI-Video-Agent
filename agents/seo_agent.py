"""SEO Agent — plan title/description/tags/hashtags/keywords (no publish)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agents.base import BaseAgent
from core.errors import SeoAgentError, StorageError
from core.logging import get_logger
from core.paths import (
    ensure_project_analysis_dir,
    ensure_project_dir,
    get_seo_plan_path,
)
from schemas.job import FeatureFlags, VideoJobConfig
from schemas.project import ProjectMetadata
from schemas.seo import SeoPack, SeoResult
from tools.seo.catalog import build_seo_pack

logger = get_logger(__name__)


class SeoAgent(BaseAgent):
    """Write analysis/seo_plan.json with title/description/tags/hashtags/keywords."""

    name = "seo"

    def run(
        self,
        project: ProjectMetadata | dict[str, Any],
        *,
        project_dir: str | Path | None = None,
        config: VideoJobConfig | dict[str, Any] | None = None,
        features: FeatureFlags | dict[str, Any] | None = None,
        script_pack: dict[str, Any] | None = None,
        platform_pack: dict[str, Any] | None = None,
        brand_pack: dict[str, Any] | None = None,
        **_: Any,
    ) -> SeoResult:
        meta = self._coerce_project(project)
        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)
        job_config = self._coerce_config(config)
        flags = self._coerce_features(features)

        platform_label = (
            (getattr(job_config, "seo_platform", None) or "").strip()
            or (job_config.platform or "").strip()
            or "YouTube"
        )

        shared_ai = None
        try:
            from tools.analysis.shared_ai import load_shared_ai_analysis

            shared_ai = load_shared_ai_analysis(root)
        except Exception:  # noqa: BLE001
            shared_ai = None

        try:
            pack = build_seo_pack(
                platform_label,
                enabled=bool(flags.seo),
                config=job_config,
                script_pack=script_pack if isinstance(script_pack, dict) else None,
                platform_pack=platform_pack if isinstance(platform_pack, dict) else None,
                brand_pack=brand_pack if isinstance(brand_pack, dict) else None,
                shared_ai=shared_ai,
            )
        except Exception as exc:  # noqa: BLE001
            raise SeoAgentError(f"SEO planning failed: {exc}") from exc

        path = self._write_pack(project_id, root, pack)
        public = {
            "title": pack.plan.title,
            "description": pack.plan.description,
            "tags": list(pack.plan.tags),
            "hashtags": list(pack.plan.hashtags),
            "keywords": list(pack.plan.keywords),
        }
        messages = [
            f"[{self.name}] {pack.notes}",
            f"[{self.name}] Output: {json.dumps(public, ensure_ascii=False)}",
            f"[{self.name}] Wrote analysis/seo_plan.json",
        ]
        logger.info(
            "SeoAgent ready project_id=%s platform=%s skipped=%s",
            project_id,
            pack.plan.platform,
            pack.plan.skipped,
        )
        return SeoResult(seo_pack=pack, seo_path=str(path), messages=messages)

    def _coerce_project(
        self, project: ProjectMetadata | dict[str, Any]
    ) -> ProjectMetadata:
        if isinstance(project, ProjectMetadata):
            return project
        try:
            return ProjectMetadata.model_validate(project)
        except Exception as exc:  # noqa: BLE001
            raise SeoAgentError(f"Invalid project metadata: {exc}") from exc

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
            raise SeoAgentError(f"Invalid job config: {exc}") from exc

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
            raise SeoAgentError(f"Invalid feature flags: {exc}") from exc

    def _write_pack(
        self,
        project_id: str,
        root: Path,
        pack: SeoPack,
    ) -> Path:
        path = root / "analysis" / "seo_plan.json"
        try:
            try:
                canonical = get_seo_plan_path(project_id)
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
            raise StorageError(f"Failed to write seo_plan.json: {path}") from exc
        return path.resolve()
