"""Country Agent — resolve country localization profile from catalog."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agents.base import BaseAgent
from core.errors import CountryAgentError, StorageError
from core.logging import get_logger
from core.paths import (
    ensure_project_analysis_dir,
    ensure_project_dir,
    get_locale_context_path,
)
from schemas.job import FeatureFlags, VideoJobConfig
from schemas.localization import CountryAgentResult, CountryProfile
from schemas.project import ProjectMetadata
from tools.localization.catalog import resolve_country

logger = get_logger(__name__)


class CountryAgent(BaseAgent):
    """Resolve country profile and seed analysis/locale_context.json."""

    name = "country"

    def run(
        self,
        project: ProjectMetadata | dict[str, Any],
        *,
        project_dir: str | Path | None = None,
        config: VideoJobConfig | dict[str, Any] | None = None,
        features: FeatureFlags | dict[str, Any] | None = None,
        **_: Any,
    ) -> CountryAgentResult:
        meta = self._coerce_project(project)
        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)
        job_config = self._coerce_config(config)
        _ = self._coerce_features(features)

        profile = resolve_country(job_config.country)
        if profile is None:
            # Soft fallback: synthesize a minimal profile from the name
            profile = CountryProfile(
                id="",
                name=job_config.country or "United States",
                default_language=job_config.language or "English",
                cultural_notes="Catalog miss — using job config country name only.",
            )
            notes = f"Country '{job_config.country}' not in catalog; using fallback profile."
        else:
            notes = f"Resolved country profile: {profile.name}"

        context = {
            "project_id": project_id,
            "country_profile": profile.model_dump(mode="json"),
            "region_profile": None,
            "primary": {
                "country": job_config.country,
                "region": job_config.region,
                "language": job_config.language,
            },
        }
        path = self._write_context(project_id, root, context)
        messages = [
            f"[{self.name}] {notes}",
            f"[{self.name}] Default language: {profile.default_language}",
            f"[{self.name}] Wrote analysis/locale_context.json",
        ]
        logger.info(
            "CountryAgent ready project_id=%s country=%s",
            project_id,
            profile.name,
        )
        return CountryAgentResult(
            country_profile=profile,
            locale_context_path=str(path),
            messages=messages,
        )

    def _coerce_project(self, project: ProjectMetadata | dict[str, Any]) -> ProjectMetadata:
        if isinstance(project, ProjectMetadata):
            return project
        try:
            return ProjectMetadata.model_validate(project)
        except Exception as exc:  # noqa: BLE001
            raise CountryAgentError(f"Invalid project metadata: {exc}") from exc

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
            raise CountryAgentError(f"Invalid job config: {exc}") from exc

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
            raise CountryAgentError(f"Invalid feature flags: {exc}") from exc

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
