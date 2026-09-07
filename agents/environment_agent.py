"""Environment Agent — resolve place preset into a structured plan (no Gemini)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agents.base import BaseAgent
from core.errors import EnvironmentAgentError, StorageError
from core.logging import get_logger
from core.paths import (
    ensure_project_analysis_dir,
    ensure_project_dir,
    get_environment_path,
)
from schemas.environment import EnvironmentPack, EnvironmentResult
from schemas.job import VideoJobConfig
from schemas.project import ProjectMetadata
from tools.environments.catalog import build_environment_pack

logger = get_logger(__name__)


class EnvironmentAgent(BaseAgent):
    """Resolve environment preset and write analysis/environment.json."""

    name = "environment"

    def run(
        self,
        project: ProjectMetadata | dict[str, Any],
        *,
        project_dir: str | Path | None = None,
        config: VideoJobConfig | dict[str, Any] | None = None,
        **_: Any,
    ) -> EnvironmentResult:
        meta = self._coerce_project(project)
        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)
        job_config = self._coerce_config(config)

        try:
            pack = build_environment_pack(job_config.environment)
        except Exception as exc:  # noqa: BLE001
            raise EnvironmentAgentError(
                f"Environment resolution failed: {exc}"
            ) from exc

        path = self._write_pack(project_id, root, pack)
        messages = [
            f"[{self.name}] {pack.notes}",
            f"[{self.name}] Preset: {pack.preset.name}",
            f"[{self.name}] Plan: {pack.plan.summary}",
            f"[{self.name}] Wrote analysis/environment.json",
        ]
        logger.info(
            "EnvironmentAgent ready project_id=%s env=%s fallback=%s",
            project_id,
            pack.preset.name,
            pack.fallback,
        )
        return EnvironmentResult(
            environment_pack=pack,
            environment_path=str(path),
            messages=messages,
        )

    def _coerce_project(
        self, project: ProjectMetadata | dict[str, Any]
    ) -> ProjectMetadata:
        if isinstance(project, ProjectMetadata):
            return project
        try:
            return ProjectMetadata.model_validate(project)
        except Exception as exc:  # noqa: BLE001
            raise EnvironmentAgentError(f"Invalid project metadata: {exc}") from exc

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
            raise EnvironmentAgentError(f"Invalid job config: {exc}") from exc

    def _write_pack(
        self,
        project_id: str,
        root: Path,
        pack: EnvironmentPack,
    ) -> Path:
        path = root / "analysis" / "environment.json"
        try:
            try:
                canonical = get_environment_path(project_id)
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
            raise StorageError(f"Failed to write environment.json: {path}") from exc
        return path.resolve()
