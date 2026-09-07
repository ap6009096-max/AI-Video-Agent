"""Platform Agent — catalog-driven export metadata (no Gemini, no auto-publish)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agents.base import BaseAgent
from core.errors import PlatformAgentError, StorageError
from core.logging import get_logger
from core.paths import (
    ensure_project_analysis_dir,
    ensure_project_dir,
    ensure_project_exports_dir,
    get_platform_export_path,
    get_platform_plan_path,
)
from schemas.job import FeatureFlags, VideoJobConfig
from schemas.platform import PlatformPack, PlatformResult
from schemas.project import ProjectMetadata
from tools.platforms.optimize import build_platform_pack

logger = get_logger(__name__)


class PlatformAgent(BaseAgent):
    """Write platform_plan.json + exports/platform_metadata.json."""

    name = "platform"

    def run(
        self,
        project: ProjectMetadata | dict[str, Any],
        *,
        project_dir: str | Path | None = None,
        config: VideoJobConfig | dict[str, Any] | None = None,
        features: FeatureFlags | dict[str, Any] | None = None,
        scripts: dict[str, Any] | None = None,
        localizations: dict[str, Any] | None = None,
        video_type_pack: dict[str, Any] | None = None,
        captions_pack: dict[str, Any] | None = None,
        reframe_pack: dict[str, Any] | None = None,
        locale_pack: dict[str, Any] | None = None,
        **_: Any,
    ) -> PlatformResult:
        _ = locale_pack  # reserved for future CTA/locale tone
        meta = self._coerce_project(project)
        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)
        job_config = self._coerce_config(config)
        flags = self._coerce_features(features)

        try:
            pack = build_platform_pack(
                job_config.platform,
                project_id=project_id,
                enabled=bool(flags.platform_optimization),
                scripts=scripts,
                localizations=localizations,
                video_type_pack=video_type_pack,
                captions_pack=captions_pack,
                reframe_pack=reframe_pack,
            )
        except Exception as exc:  # noqa: BLE001
            raise PlatformAgentError(f"Platform optimization failed: {exc}") from exc

        # Hard guarantees — never publish
        pack.preset.publish_enabled = False
        pack.plan.export_hints.publish_enabled = False
        pack.plan.export_hints.publish_status = "not_published"

        export_path = ""
        if not pack.plan.skipped:
            export_path = str(self._write_export(project_id, root, pack))
            pack.export_path = export_path

        path = self._write_pack(project_id, root, pack)
        messages = [
            f"[{self.name}] {pack.notes}",
            f"[{self.name}] Platform={pack.preset.name} "
            f"aspect={pack.plan.metadata.aspect_recommendation} "
            f"publish={pack.plan.export_hints.publish_status}",
            f"[{self.name}] Wrote analysis/platform_plan.json",
        ]
        if export_path:
            messages.append(f"[{self.name}] Wrote exports/platform_metadata.json")
        logger.info(
            "PlatformAgent ready project_id=%s platform=%s skipped=%s",
            project_id,
            pack.preset.name,
            pack.plan.skipped,
        )
        return PlatformResult(
            platform_pack=pack, platform_path=str(path), messages=messages
        )

    def _coerce_project(
        self, project: ProjectMetadata | dict[str, Any]
    ) -> ProjectMetadata:
        if isinstance(project, ProjectMetadata):
            return project
        try:
            return ProjectMetadata.model_validate(project)
        except Exception as exc:  # noqa: BLE001
            raise PlatformAgentError(f"Invalid project metadata: {exc}") from exc

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
            raise PlatformAgentError(f"Invalid job config: {exc}") from exc

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
            raise PlatformAgentError(f"Invalid feature flags: {exc}") from exc

    def _write_pack(
        self,
        project_id: str,
        root: Path,
        pack: PlatformPack,
    ) -> Path:
        path = root / "analysis" / "platform_plan.json"
        try:
            try:
                canonical = get_platform_plan_path(project_id)
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
            raise StorageError(f"Failed to write platform_plan.json: {path}") from exc
        return path.resolve()

    def _write_export(
        self,
        project_id: str,
        root: Path,
        pack: PlatformPack,
    ) -> Path:
        path = root / "exports" / "platform_metadata.json"
        try:
            try:
                canonical = get_platform_export_path(project_id)
                if canonical.parent.parent == root.resolve():
                    path = canonical
            except Exception:  # noqa: BLE001
                pass
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                ensure_project_exports_dir(project_id)
            except Exception:  # noqa: BLE001
                pass
            payload = {
                "platform": pack.preset.name,
                "official_url": pack.preset.official_url,
                "publish_enabled": False,
                "publish_status": "not_published",
                "metadata": pack.plan.metadata.model_dump(mode="json"),
                "export_hints": pack.plan.export_hints.model_dump(mode="json"),
                "notes": (
                    "Opening official_url is not publishing. "
                    "Automatic publishing requires official APIs, OAuth, "
                    "and user authorization (later)."
                ),
            }
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError as exc:
            raise StorageError(
                f"Failed to write platform_metadata.json: {path}"
            ) from exc
        return path.resolve()
