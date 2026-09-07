"""Avatar Agent — plan presenter type and capability flags (no ML render)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agents.base import BaseAgent
from core.errors import AvatarAgentError, StorageError
from core.logging import get_logger
from core.paths import (
    ensure_project_analysis_dir,
    ensure_project_dir,
    get_avatar_plan_path,
)
from schemas.avatar import AvatarPack, AvatarResult
from schemas.job import FeatureFlags, VideoJobConfig
from schemas.project import ProjectMetadata
from tools.avatar.catalog import build_avatar_pack

logger = get_logger(__name__)


class AvatarAgent(BaseAgent):
    """Write analysis/avatar_plan.json with avatar_type/voice/language/emotion."""

    name = "avatar"

    def run(
        self,
        project: ProjectMetadata | dict[str, Any],
        *,
        project_dir: str | Path | None = None,
        config: VideoJobConfig | dict[str, Any] | None = None,
        features: FeatureFlags | dict[str, Any] | None = None,
        voice_pack: dict[str, Any] | None = None,
        locale_pack: dict[str, Any] | None = None,
        localizations: dict[str, Any] | None = None,
        **_: Any,
    ) -> AvatarResult:
        _ = localizations  # reserved for multi-track speaking later
        meta = self._coerce_project(project)
        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)
        job_config = self._coerce_config(config)
        flags = self._coerce_features(features)

        try:
            pack = build_avatar_pack(
                job_config.avatar,
                enabled=bool(flags.avatar),
                voice_pack=voice_pack if isinstance(voice_pack, dict) else None,
                locale_pack=locale_pack if isinstance(locale_pack, dict) else None,
                config=job_config,
            )
        except Exception as exc:  # noqa: BLE001
            raise AvatarAgentError(f"Avatar planning failed: {exc}") from exc

        path = self._write_pack(project_id, root, pack)
        public = {
            "avatar_type": pack.plan.avatar_type,
            "voice": pack.plan.voice,
            "language": pack.plan.language,
            "emotion": pack.plan.emotion,
        }
        messages = [
            f"[{self.name}] {pack.notes}",
            f"[{self.name}] Output: {json.dumps(public, ensure_ascii=False)}",
            f"[{self.name}] Wrote analysis/avatar_plan.json",
        ]
        logger.info(
            "AvatarAgent ready project_id=%s type=%s skipped=%s",
            project_id,
            pack.plan.avatar_type,
            pack.plan.skipped,
        )
        return AvatarResult(
            avatar_pack=pack, avatar_path=str(path), messages=messages
        )

    def _coerce_project(
        self, project: ProjectMetadata | dict[str, Any]
    ) -> ProjectMetadata:
        if isinstance(project, ProjectMetadata):
            return project
        try:
            return ProjectMetadata.model_validate(project)
        except Exception as exc:  # noqa: BLE001
            raise AvatarAgentError(f"Invalid project metadata: {exc}") from exc

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
            raise AvatarAgentError(f"Invalid job config: {exc}") from exc

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
            raise AvatarAgentError(f"Invalid feature flags: {exc}") from exc

    def _write_pack(
        self,
        project_id: str,
        root: Path,
        pack: AvatarPack,
    ) -> Path:
        path = root / "analysis" / "avatar_plan.json"
        try:
            try:
                canonical = get_avatar_plan_path(project_id)
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
            raise StorageError(f"Failed to write avatar_plan.json: {path}") from exc
        return path.resolve()
