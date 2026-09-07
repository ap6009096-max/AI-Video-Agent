"""Video Type Agent — resolve creative format preset from catalog (no Gemini)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agents.base import BaseAgent
from core.errors import StorageError, VideoTypeAgentError
from core.logging import get_logger
from core.paths import (
    ensure_project_analysis_dir,
    ensure_project_dir,
    get_video_type_path,
)
from schemas.job import VideoJobConfig
from schemas.project import ProjectMetadata
from schemas.video_type import VideoTypePack, VideoTypeResult
from tools.video_types.catalog import build_video_type_pack

logger = get_logger(__name__)


class VideoTypeAgent(BaseAgent):
    """Resolve video type preset and write analysis/video_type.json."""

    name = "video_type"

    def run(
        self,
        project: ProjectMetadata | dict[str, Any],
        *,
        project_dir: str | Path | None = None,
        config: VideoJobConfig | dict[str, Any] | None = None,
        **_: Any,
    ) -> VideoTypeResult:
        meta = self._coerce_project(project)
        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)
        job_config = self._coerce_config(config)

        try:
            pack = build_video_type_pack(
                job_config.video_type,
                platform=job_config.platform or "",
            )
        except Exception as exc:  # noqa: BLE001
            raise VideoTypeAgentError(
                f"Video type resolution failed: {exc}"
            ) from exc

        path = self._write_pack(project_id, root, pack)
        messages = [
            f"[{self.name}] {pack.notes}",
            f"[{self.name}] Preset: {pack.preset.name} "
            f"({pack.preset.aspect_ratio}, pacing={pack.preset.pacing})",
            f"[{self.name}] Wrote analysis/video_type.json",
        ]
        logger.info(
            "VideoTypeAgent ready project_id=%s type=%s fallback=%s",
            project_id,
            pack.preset.name,
            pack.fallback,
        )
        return VideoTypeResult(
            video_type_pack=pack,
            video_type_path=str(path),
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
            raise VideoTypeAgentError(f"Invalid project metadata: {exc}") from exc

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
            raise VideoTypeAgentError(f"Invalid job config: {exc}") from exc

    def _write_pack(
        self,
        project_id: str,
        root: Path,
        pack: VideoTypePack,
    ) -> Path:
        path = root / "analysis" / "video_type.json"
        try:
            try:
                canonical = get_video_type_path(project_id)
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
            raise StorageError(f"Failed to write video_type.json: {path}") from exc
        return path.resolve()
