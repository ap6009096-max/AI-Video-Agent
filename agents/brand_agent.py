"""Brand Agent — voice, identity, colors, CTA, messaging kit."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agents.base import BaseAgent
from core.errors import BrandAgentError, StorageError
from core.logging import get_logger
from core.paths import (
    ensure_project_analysis_dir,
    ensure_project_dir,
    get_brand_plan_path,
)
from schemas.brand import BrandPack, BrandResult
from schemas.job import FeatureFlags, VideoJobConfig
from schemas.project import ProjectMetadata
from tools.brand.catalog import EnrichFn, build_brand_pack

logger = get_logger(__name__)


class BrandAgent(BaseAgent):
    """Write analysis/brand_plan.json with brand kit domains."""

    name = "brand"

    def run(
        self,
        project: ProjectMetadata | dict[str, Any],
        *,
        project_dir: str | Path | None = None,
        config: VideoJobConfig | dict[str, Any] | None = None,
        features: FeatureFlags | dict[str, Any] | None = None,
        platform_pack: dict[str, Any] | None = None,
        visual_style_pack: dict[str, Any] | None = None,
        enrich_fn: EnrichFn | None = None,
        build_fn: Any | None = None,
        **_: Any,
    ) -> BrandResult:
        meta = self._coerce_project(project)
        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)
        job_config = self._coerce_config(config)
        flags = self._coerce_features(features)

        builder = build_fn or build_brand_pack
        try:
            pack = builder(
                enabled=bool(flags.brand),
                config=job_config,
                platform_pack=(
                    platform_pack if isinstance(platform_pack, dict) else None
                ),
                visual_style_pack=(
                    visual_style_pack if isinstance(visual_style_pack, dict) else None
                ),
                enrich_fn=enrich_fn,
            )
        except Exception as exc:  # noqa: BLE001
            raise BrandAgentError(f"Brand planning failed: {exc}") from exc

        if not isinstance(pack, BrandPack):
            pack = BrandPack.model_validate(pack)

        path = self._write_pack(project_id, root, pack)
        public = {
            "voice": pack.plan.voice.model_dump(),
            "visual_identity": pack.plan.visual_identity.model_dump(),
            "colors": pack.plan.colors.model_dump(),
            "cta": pack.plan.cta.model_dump(),
            "messaging": pack.plan.messaging.model_dump(),
        }
        messages = [
            f"[{self.name}] {pack.notes}",
            f"[{self.name}] Output: {json.dumps(public, ensure_ascii=False)}",
            f"[{self.name}] Wrote analysis/brand_plan.json",
        ]
        logger.info(
            "BrandAgent ready project_id=%s brand=%s provider=%s skipped=%s",
            project_id,
            pack.plan.brand_name,
            pack.plan.provider,
            pack.plan.skipped,
        )
        return BrandResult(
            brand_pack=pack, brand_path=str(path), messages=messages
        )

    def _coerce_project(
        self, project: ProjectMetadata | dict[str, Any]
    ) -> ProjectMetadata:
        if isinstance(project, ProjectMetadata):
            return project
        try:
            return ProjectMetadata.model_validate(project)
        except Exception as exc:  # noqa: BLE001
            raise BrandAgentError(f"Invalid project metadata: {exc}") from exc

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
            raise BrandAgentError(f"Invalid job config: {exc}") from exc

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
            raise BrandAgentError(f"Invalid feature flags: {exc}") from exc

    def _write_pack(
        self,
        project_id: str,
        root: Path,
        pack: BrandPack,
    ) -> Path:
        path = root / "analysis" / "brand_plan.json"
        try:
            try:
                canonical = get_brand_plan_path(project_id)
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
            raise StorageError(f"Failed to write brand_plan.json: {path}") from exc
        return path.resolve()
