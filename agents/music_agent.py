"""Music Agent — mood selection / plan only; no generation required (MVP)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agents.base import BaseAgent
from core.errors import MusicAgentError, StorageError
from core.logging import get_logger
from core.paths import (
    ensure_project_analysis_dir,
    ensure_project_dir,
    get_music_plan_path,
)
from schemas.av_plan import MusicPack, MusicResult
from schemas.job import FeatureFlags, VideoJobConfig
from schemas.project import ProjectMetadata
from tools.music.catalog import build_music_pack

logger = get_logger(__name__)


class MusicAgent(BaseAgent):
    """Write analysis/music_plan.json — never requires music generation for MVP."""

    name = "music"

    def run(
        self,
        project: ProjectMetadata | dict[str, Any],
        *,
        project_dir: str | Path | None = None,
        config: VideoJobConfig | dict[str, Any] | None = None,
        features: FeatureFlags | dict[str, Any] | None = None,
        **_: Any,
    ) -> MusicResult:
        meta = self._coerce_project(project)
        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)
        job_config = self._coerce_config(config)
        flags = self._coerce_features(features)

        try:
            pack = build_music_pack(
                job_config.music,
                enabled=bool(flags.music),
            )
        except Exception as exc:  # noqa: BLE001
            raise MusicAgentError(f"Music planning failed: {exc}") from exc

        # Hard guarantee for MVP
        pack.plan.generation_required = False
        pack.preset.generation_required = False

        path = self._write_pack(project_id, root, pack)
        messages = [
            f"[{self.name}] {pack.notes}",
            f"[{self.name}] Preset: {pack.preset.name} "
            f"mode={pack.plan.mode} generation_required={pack.plan.generation_required}",
            f"[{self.name}] Wrote analysis/music_plan.json",
        ]
        logger.info(
            "MusicAgent ready project_id=%s music=%s gen_required=%s",
            project_id,
            pack.preset.name,
            pack.plan.generation_required,
        )
        return MusicResult(music_pack=pack, music_path=str(path), messages=messages)

    def _coerce_project(
        self, project: ProjectMetadata | dict[str, Any]
    ) -> ProjectMetadata:
        if isinstance(project, ProjectMetadata):
            return project
        try:
            return ProjectMetadata.model_validate(project)
        except Exception as exc:  # noqa: BLE001
            raise MusicAgentError(f"Invalid project metadata: {exc}") from exc

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
            raise MusicAgentError(f"Invalid job config: {exc}") from exc

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
            raise MusicAgentError(f"Invalid feature flags: {exc}") from exc

    def _write_pack(
        self,
        project_id: str,
        root: Path,
        pack: MusicPack,
    ) -> Path:
        path = root / "analysis" / "music_plan.json"
        try:
            try:
                canonical = get_music_plan_path(project_id)
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
            raise StorageError(f"Failed to write music_plan.json: {path}") from exc
        return path.resolve()
