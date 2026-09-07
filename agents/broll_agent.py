"""B-Roll Agent — structured B-roll plans with honest source kinds (no Gemini)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agents.base import BaseAgent
from core.errors import BRollAgentError, StorageError
from core.logging import get_logger
from core.paths import (
    ensure_project_analysis_dir,
    ensure_project_dir,
    get_broll_plan_path,
)
from schemas.av_plan import BRollPack, BRollResult
from schemas.clips import ClipsReport
from schemas.environment import EnvironmentPack
from schemas.job import FeatureFlags, VideoJobConfig
from schemas.project import ProjectMetadata
from schemas.story import ScriptsReport
from tools.broll.catalog import build_broll_pack

logger = get_logger(__name__)


class BRollAgent(BaseAgent):
    """Write analysis/broll_plan.json — never pretends unavailable footage exists."""

    name = "b_roll"

    def run(
        self,
        project: ProjectMetadata | dict[str, Any],
        *,
        project_dir: str | Path | None = None,
        config: VideoJobConfig | dict[str, Any] | None = None,
        features: FeatureFlags | dict[str, Any] | None = None,
        clips: dict[str, Any] | ClipsReport | None = None,
        scripts: dict[str, Any] | ScriptsReport | None = None,
        environment_pack: dict[str, Any] | EnvironmentPack | None = None,
        **_: Any,
    ) -> BRollResult:
        meta = self._coerce_project(project)
        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)
        _ = self._coerce_config(config)
        flags = self._coerce_features(features)
        _ = scripts  # reserved for future timed cue alignment

        clip_dicts = self._clip_dicts(clips)
        broll_req = self._broll_requirements(environment_pack)

        try:
            pack = build_broll_pack(
                project_id=project_id,
                clips=clip_dicts,
                broll_requirements=broll_req,
                enabled=bool(flags.b_roll),
            )
        except Exception as exc:  # noqa: BLE001
            raise BRollAgentError(f"B-roll planning failed: {exc}") from exc

        # Enforce honesty: available only with a real path
        for item in pack.plan.items:
            if item.available and not (item.asset_path or "").strip():
                item.available = False
                item.notes = (
                    (item.notes + " ").strip()
                    + " Cleared available flag — no asset_path."
                ).strip()

        path = self._write_pack(project_id, root, pack)
        messages = [
            f"[{self.name}] {pack.notes}",
            f"[{self.name}] Items: {len(pack.plan.items)} skipped={pack.plan.skipped}",
            f"[{self.name}] Wrote analysis/broll_plan.json",
        ]
        logger.info(
            "BRollAgent ready project_id=%s items=%s skipped=%s",
            project_id,
            len(pack.plan.items),
            pack.plan.skipped,
        )
        return BRollResult(broll_pack=pack, broll_path=str(path), messages=messages)

    def _coerce_project(
        self, project: ProjectMetadata | dict[str, Any]
    ) -> ProjectMetadata:
        if isinstance(project, ProjectMetadata):
            return project
        try:
            return ProjectMetadata.model_validate(project)
        except Exception as exc:  # noqa: BLE001
            raise BRollAgentError(f"Invalid project metadata: {exc}") from exc

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
            raise BRollAgentError(f"Invalid job config: {exc}") from exc

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
            raise BRollAgentError(f"Invalid feature flags: {exc}") from exc

    def _clip_dicts(
        self, clips: dict[str, Any] | ClipsReport | None
    ) -> list[dict[str, Any]]:
        if clips is None:
            return []
        if isinstance(clips, ClipsReport):
            return [c.model_dump(mode="json") for c in clips.clips]
        if isinstance(clips, dict):
            raw = clips.get("clips") or []
            if isinstance(raw, list):
                return [c if isinstance(c, dict) else {} for c in raw]
        return []

    def _broll_requirements(
        self, environment_pack: dict[str, Any] | EnvironmentPack | None
    ) -> str:
        if isinstance(environment_pack, EnvironmentPack):
            return (
                environment_pack.plan.broll_requirements
                or environment_pack.preset.broll_requirements
                or ""
            )
        if isinstance(environment_pack, dict) and environment_pack:
            plan = environment_pack.get("plan") or {}
            preset = environment_pack.get("preset") or {}
            return str(
                plan.get("broll_requirements")
                or preset.get("broll_requirements")
                or ""
            )
        return ""

    def _write_pack(
        self,
        project_id: str,
        root: Path,
        pack: BRollPack,
    ) -> Path:
        path = root / "analysis" / "broll_plan.json"
        try:
            try:
                canonical = get_broll_plan_path(project_id)
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
            raise StorageError(f"Failed to write broll_plan.json: {path}") from exc
        return path.resolve()
