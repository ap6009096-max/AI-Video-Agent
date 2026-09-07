"""Motion Graphics Agent — graphic-layer overlay plan."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agents.base import BaseAgent
from core.errors import MotionGraphicsAgentError, StorageError
from core.logging import get_logger
from core.paths import (
    ensure_project_analysis_dir,
    ensure_project_dir,
    get_motion_graphics_plan_path,
)
from schemas.job import FeatureFlags, VideoJobConfig
from schemas.motion_graphics import MotionGraphicsPack, MotionGraphicsResult
from schemas.project import ProjectMetadata
from tools.motion_graphics.catalog import AnalyzeFn, build_motion_graphics_pack

logger = get_logger(__name__)


class MotionGraphicsAgent(BaseAgent):
    """Write analysis/motion_graphics_plan.json (plan-only overlays)."""

    name = "motion_graphics"

    def run(
        self,
        project: ProjectMetadata | dict[str, Any],
        *,
        project_dir: str | Path | None = None,
        config: VideoJobConfig | dict[str, Any] | None = None,
        features: FeatureFlags | dict[str, Any] | None = None,
        script_pack: dict[str, Any] | None = None,
        storyboard_pack: dict[str, Any] | None = None,
        director_pack: dict[str, Any] | None = None,
        camera_pack: dict[str, Any] | None = None,
        character_pack: dict[str, Any] | None = None,
        visual_style_pack: dict[str, Any] | None = None,
        analyze_fn: AnalyzeFn | None = None,
        **_: Any,
    ) -> MotionGraphicsResult:
        meta = self._coerce_project(project)
        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)
        job_config = self._coerce_config(config)
        flags = self._coerce_features(features)

        try:
            pack = build_motion_graphics_pack(
                enabled=bool(flags.motion_graphics),
                config=job_config,
                script_pack=script_pack if isinstance(script_pack, dict) else None,
                storyboard_pack=(
                    storyboard_pack if isinstance(storyboard_pack, dict) else None
                ),
                director_pack=(
                    director_pack if isinstance(director_pack, dict) else None
                ),
                camera_pack=camera_pack if isinstance(camera_pack, dict) else None,
                character_pack=(
                    character_pack if isinstance(character_pack, dict) else None
                ),
                visual_style_pack=(
                    visual_style_pack if isinstance(visual_style_pack, dict) else None
                ),
                analyze_fn=analyze_fn,
            )
        except Exception as exc:  # noqa: BLE001
            raise MotionGraphicsAgentError(
                f"Motion graphics planning failed: {exc}"
            ) from exc

        path = self._write_pack(project_id, root, pack)
        public = MotionGraphicsResult(
            motion_graphics_pack=pack, motion_graphics_path=str(path)
        ).public_output()
        messages = [
            f"[{self.name}] {pack.notes}",
            f"[{self.name}] Overlays: {len(pack.plan.overlays)}",
            f"[{self.name}] Wrote analysis/motion_graphics_plan.json",
        ]
        if public.get("overlays"):
            messages.append(
                f"[{self.name}] Sample: "
                f"{json.dumps(public['overlays'][0], ensure_ascii=False)[:160]}"
            )
        logger.info(
            "MotionGraphicsAgent ready project_id=%s overlays=%s skipped=%s",
            project_id,
            len(pack.plan.overlays),
            pack.plan.skipped,
        )
        return MotionGraphicsResult(
            motion_graphics_pack=pack,
            motion_graphics_path=str(path),
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
            raise MotionGraphicsAgentError(f"Invalid project metadata: {exc}") from exc

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
            raise MotionGraphicsAgentError(f"Invalid job config: {exc}") from exc

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
            raise MotionGraphicsAgentError(f"Invalid feature flags: {exc}") from exc

    def _write_pack(
        self,
        project_id: str,
        root: Path,
        pack: MotionGraphicsPack,
    ) -> Path:
        path = root / "analysis" / "motion_graphics_plan.json"
        try:
            try:
                canonical = get_motion_graphics_plan_path(project_id)
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
            raise StorageError(
                f"Failed to write motion_graphics_plan.json: {path}"
            ) from exc
        return path.resolve()
