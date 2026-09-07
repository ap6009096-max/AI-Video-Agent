"""Director Agent — scene sequencing and continuity plan."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agents.base import BaseAgent
from core.errors import DirectorAgentError, StorageError
from core.logging import get_logger
from core.paths import (
    ensure_project_analysis_dir,
    ensure_project_dir,
    get_director_plan_path,
)
from schemas.director import DirectorPack, DirectorResult
from schemas.job import FeatureFlags, VideoJobConfig
from schemas.project import ProjectMetadata
from tools.director.catalog import AnalyzeFn, build_director_pack

logger = get_logger(__name__)


class DirectorAgent(BaseAgent):
    """Write analysis/director_plan.json (plan-only continuity direction)."""

    name = "director"

    def run(
        self,
        project: ProjectMetadata | dict[str, Any],
        *,
        project_dir: str | Path | None = None,
        config: VideoJobConfig | dict[str, Any] | None = None,
        features: FeatureFlags | dict[str, Any] | None = None,
        script_pack: dict[str, Any] | None = None,
        storyboard_pack: dict[str, Any] | None = None,
        stories: dict[str, Any] | None = None,
        visual_style_pack: dict[str, Any] | None = None,
        environment_pack: dict[str, Any] | None = None,
        character_pack: dict[str, Any] | None = None,
        camera_pack: dict[str, Any] | None = None,
        analyze_fn: AnalyzeFn | None = None,
        **_: Any,
    ) -> DirectorResult:
        meta = self._coerce_project(project)
        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)
        job_config = self._coerce_config(config)
        flags = self._coerce_features(features)

        try:
            pack = build_director_pack(
                enabled=bool(flags.director),
                config=job_config,
                script_pack=script_pack if isinstance(script_pack, dict) else None,
                storyboard_pack=(
                    storyboard_pack if isinstance(storyboard_pack, dict) else None
                ),
                stories=stories if isinstance(stories, dict) else None,
                visual_style_pack=(
                    visual_style_pack if isinstance(visual_style_pack, dict) else None
                ),
                environment_pack=(
                    environment_pack if isinstance(environment_pack, dict) else None
                ),
                character_pack=(
                    character_pack if isinstance(character_pack, dict) else None
                ),
                camera_pack=camera_pack if isinstance(camera_pack, dict) else None,
                analyze_fn=analyze_fn,
            )
        except Exception as exc:  # noqa: BLE001
            raise DirectorAgentError(f"Director planning failed: {exc}") from exc

        path = self._write_pack(project_id, root, pack)
        public = DirectorResult(
            director_pack=pack, director_path=str(path)
        ).public_output()
        messages = [
            f"[{self.name}] {pack.notes}",
            f"[{self.name}] Scenes: {len(pack.plan.scene_order)}",
            f"[{self.name}] Wrote analysis/director_plan.json",
        ]
        if public.get("continuity_notes"):
            messages.append(
                f"[{self.name}] Sample note: "
                f"{json.dumps(public['continuity_notes'][0][:120], ensure_ascii=False)}"
            )
        logger.info(
            "DirectorAgent ready project_id=%s scenes=%s skipped=%s",
            project_id,
            len(pack.plan.scene_order),
            pack.plan.skipped,
        )
        return DirectorResult(
            director_pack=pack, director_path=str(path), messages=messages
        )

    def _coerce_project(
        self, project: ProjectMetadata | dict[str, Any]
    ) -> ProjectMetadata:
        if isinstance(project, ProjectMetadata):
            return project
        try:
            return ProjectMetadata.model_validate(project)
        except Exception as exc:  # noqa: BLE001
            raise DirectorAgentError(f"Invalid project metadata: {exc}") from exc

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
            raise DirectorAgentError(f"Invalid job config: {exc}") from exc

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
            raise DirectorAgentError(f"Invalid feature flags: {exc}") from exc

    def _write_pack(
        self,
        project_id: str,
        root: Path,
        pack: DirectorPack,
    ) -> Path:
        path = root / "analysis" / "director_plan.json"
        try:
            try:
                canonical = get_director_plan_path(project_id)
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
            raise StorageError(f"Failed to write director_plan.json: {path}") from exc
        return path.resolve()
