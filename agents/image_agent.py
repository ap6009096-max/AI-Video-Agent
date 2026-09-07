"""Image Agent — plan prompts and write visuals under images/."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agents.base import BaseAgent
from core.errors import ImageAgentError, StorageError
from core.logging import get_logger
from core.paths import (
    ensure_project_analysis_dir,
    ensure_project_dir,
    ensure_project_images_dir,
    get_image_plan_path,
)
from schemas.image import ImagePack, ImageResult
from schemas.job import FeatureFlags, VideoJobConfig
from schemas.project import ProjectMetadata
from tools.images.catalog import AnalyzeFn, GenerateFn, build_image_pack

logger = get_logger(__name__)


class ImageAgent(BaseAgent):
    """Write analysis/image_plan.json and assets under images/."""

    name = "image_generation"

    def run(
        self,
        project: ProjectMetadata | dict[str, Any],
        *,
        project_dir: str | Path | None = None,
        config: VideoJobConfig | dict[str, Any] | None = None,
        features: FeatureFlags | dict[str, Any] | None = None,
        script_pack: dict[str, Any] | None = None,
        transcript: dict[str, Any] | None = None,
        scenes: dict[str, Any] | None = None,
        stories: dict[str, Any] | None = None,
        visual_style_pack: dict[str, Any] | None = None,
        environment_pack: dict[str, Any] | None = None,
        analyze_fn: AnalyzeFn | None = None,
        generate_fn: GenerateFn | None = None,
        **_: Any,
    ) -> ImageResult:
        meta = self._coerce_project(project)
        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)
        job_config = self._coerce_config(config)
        flags = self._coerce_features(features)

        images_dir = root / "images"
        try:
            try:
                canonical = ensure_project_images_dir(project_id)
                if canonical.parent == root.resolve():
                    images_dir = canonical
            except Exception:  # noqa: BLE001
                images_dir.mkdir(parents=True, exist_ok=True)

            pack = build_image_pack(
                enabled=bool(flags.image_generation),
                images_dir=images_dir,
                config=job_config,
                script_pack=script_pack if isinstance(script_pack, dict) else None,
                transcript=transcript if isinstance(transcript, dict) else None,
                scenes=scenes if isinstance(scenes, dict) else None,
                stories=stories if isinstance(stories, dict) else None,
                visual_style_pack=(
                    visual_style_pack if isinstance(visual_style_pack, dict) else None
                ),
                environment_pack=(
                    environment_pack if isinstance(environment_pack, dict) else None
                ),
                analyze_fn=analyze_fn,
                generate_fn=generate_fn,
            )
        except Exception as exc:  # noqa: BLE001
            raise ImageAgentError(f"Image planning failed: {exc}") from exc

        path = self._write_pack(project_id, root, pack)
        public = [
            {
                "scene_id": i.scene_id,
                "prompt": i.prompt,
                "style": i.style,
                "environment": i.environment,
                "image_path": i.image_path,
            }
            for i in pack.plan.items
        ]
        messages = [
            f"[{self.name}] {pack.notes}",
            f"[{self.name}] Items: {len(public)}",
            f"[{self.name}] Wrote analysis/image_plan.json",
        ]
        if public:
            messages.append(
                f"[{self.name}] Sample: {json.dumps(public[0], ensure_ascii=False)}"
            )
        logger.info(
            "ImageAgent ready project_id=%s items=%s skipped=%s",
            project_id,
            len(public),
            pack.plan.skipped,
        )
        return ImageResult(image_pack=pack, image_path=str(path), messages=messages)

    def _coerce_project(
        self, project: ProjectMetadata | dict[str, Any]
    ) -> ProjectMetadata:
        if isinstance(project, ProjectMetadata):
            return project
        try:
            return ProjectMetadata.model_validate(project)
        except Exception as exc:  # noqa: BLE001
            raise ImageAgentError(f"Invalid project metadata: {exc}") from exc

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
            raise ImageAgentError(f"Invalid job config: {exc}") from exc

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
            raise ImageAgentError(f"Invalid feature flags: {exc}") from exc

    def _write_pack(
        self,
        project_id: str,
        root: Path,
        pack: ImagePack,
    ) -> Path:
        path = root / "analysis" / "image_plan.json"
        try:
            try:
                canonical = get_image_plan_path(project_id)
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
            raise StorageError(f"Failed to write image_plan.json: {path}") from exc
        return path.resolve()
