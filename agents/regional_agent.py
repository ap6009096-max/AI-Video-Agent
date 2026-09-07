"""Regional Agent — resolve country-scoped region and merge locale pack."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agents.base import BaseAgent
from core.errors import RegionalAgentError, StorageError
from core.logging import get_logger
from core.paths import (
    ensure_project_analysis_dir,
    ensure_project_dir,
    get_locale_context_path,
)
from schemas.job import FeatureFlags, VideoJobConfig
from schemas.localization import (
    CountryProfile,
    LocalePack,
    LocalizationTarget,
    RegionalAgentResult,
)
from schemas.project import ProjectMetadata
from tools.localization.catalog import build_locale_pack, resolve_region

logger = get_logger(__name__)


class RegionalAgent(BaseAgent):
    """Resolve regional profile and update locale_context.json."""

    name = "regional"

    def run(
        self,
        project: ProjectMetadata | dict[str, Any],
        *,
        project_dir: str | Path | None = None,
        config: VideoJobConfig | dict[str, Any] | None = None,
        features: FeatureFlags | dict[str, Any] | None = None,
        country_profile: dict[str, Any] | CountryProfile | None = None,
        **_: Any,
    ) -> RegionalAgentResult:
        meta = self._coerce_project(project)
        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)
        job_config = self._coerce_config(config)
        flags = self._coerce_features(features)
        country = self._coerce_country(country_profile, job_config.country)

        region = resolve_region(job_config.region, country=country)
        include_humor = bool(flags.regional_humor)
        pack = build_locale_pack(
            LocalizationTarget(
                country=country.name if country else job_config.country,
                region=job_config.region,
                language=job_config.language,
            ),
            include_regional_humor=include_humor,
            voice=job_config.voice,
            country_override=country,
            region_override=region,
        )

        if region is None:
            notes = (
                f"No catalog subregion for '{job_config.region}' "
                f"(continental/global treated as none)."
            )
        else:
            notes = f"Resolved region profile: {region.name} → {region.language or 'n/a'}"

        context = {
            "project_id": project_id,
            "country_profile": country.model_dump(mode="json") if country else None,
            "region_profile": region.model_dump(mode="json") if region else None,
            "locale_pack": pack.model_dump(mode="json"),
            "primary": {
                "country": job_config.country,
                "region": job_config.region,
                "language": job_config.language,
            },
            "include_regional_humor": include_humor,
        }
        path = self._write_context(project_id, root, context)
        messages = [
            f"[{self.name}] {notes}",
            f"[{self.name}] Regional humor: {'on' if include_humor else 'off'}",
            f"[{self.name}] Updated analysis/locale_context.json",
        ]
        logger.info(
            "RegionalAgent ready project_id=%s region=%s",
            project_id,
            region.name if region else None,
        )
        return RegionalAgentResult(
            region_profile=region,
            locale_pack=pack,
            locale_context_path=str(path),
            messages=messages,
        )

    def _coerce_country(
        self,
        country_profile: dict[str, Any] | CountryProfile | None,
        country_name: str,
    ) -> CountryProfile | None:
        if isinstance(country_profile, CountryProfile):
            return country_profile
        if isinstance(country_profile, dict) and country_profile:
            try:
                return CountryProfile.model_validate(country_profile)
            except Exception:  # noqa: BLE001
                pass
        from tools.localization.catalog import resolve_country

        return resolve_country(country_name)

    def _coerce_project(self, project: ProjectMetadata | dict[str, Any]) -> ProjectMetadata:
        if isinstance(project, ProjectMetadata):
            return project
        try:
            return ProjectMetadata.model_validate(project)
        except Exception as exc:  # noqa: BLE001
            raise RegionalAgentError(f"Invalid project metadata: {exc}") from exc

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
            raise RegionalAgentError(f"Invalid job config: {exc}") from exc

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
            raise RegionalAgentError(f"Invalid feature flags: {exc}") from exc

    def _write_context(
        self,
        project_id: str,
        root: Path,
        context: dict[str, Any],
    ) -> Path:
        path = root / "analysis" / "locale_context.json"
        try:
            try:
                canonical = get_locale_context_path(project_id)
                if canonical.parent.parent == root.resolve():
                    path = canonical
            except Exception:  # noqa: BLE001
                pass
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                ensure_project_analysis_dir(project_id)
            except Exception:  # noqa: BLE001
                pass
            path.write_text(json.dumps(context, indent=2), encoding="utf-8")
        except OSError as exc:
            raise StorageError(f"Failed to write locale_context.json: {path}") from exc
        return path.resolve()
