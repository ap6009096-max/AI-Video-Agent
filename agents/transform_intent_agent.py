"""Transform Intent Agent — NL scene edit → analysis/transform_intent.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agents.base import BaseAgent
from core.errors import StorageError, TransformIntentAgentError
from core.logging import get_logger
from core.paths import (
    ensure_project_analysis_dir,
    ensure_project_dir,
    get_transform_intent_path,
)
from schemas.job import FeatureFlags, VideoJobConfig
from schemas.project import ProjectMetadata
from schemas.transform_intent import (
    GeminiTransformBatch,
    TransformIntentPack,
    TransformIntentResult,
)
from tools.transform.catalog import AnalyzeFn, build_transform_intent_pack
from tools.transform.selective import resolve_scene_window

logger = get_logger(__name__)


class TransformIntentAgent(BaseAgent):
    """Write analysis/transform_intent.json (changed vs preserved)."""

    name = "transform_intent"

    def run(
        self,
        project: ProjectMetadata | dict[str, Any],
        *,
        project_dir: str | Path | None = None,
        config: VideoJobConfig | dict[str, Any] | None = None,
        features: FeatureFlags | dict[str, Any] | None = None,
        instruction: str = "",
        target_scene: int | str | None = None,
        target_speaker: str = "",
        scenes: dict[str, Any] | None = None,
        speakers: dict[str, Any] | None = None,
        transcript: dict[str, Any] | None = None,
        speech_transcript: dict[str, Any] | None = None,
        analyze_fn: AnalyzeFn | None = None,
        **_: Any,
    ) -> TransformIntentResult:
        meta = self._coerce_project(project)
        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)
        job_config = self._coerce_config(config)
        flags = self._coerce_features(features)

        # Prefer explicit instruction; else job fields
        instr = (instruction or "").strip()
        if not instr:
            instr = str(getattr(job_config, "transform_instruction", "") or "").strip()
        scene_hint = target_scene
        if scene_hint is None or scene_hint == "":
            raw = getattr(job_config, "transform_scene_id", "") or ""
            scene_hint = raw if raw != "" else None
        speaker_hint = (target_speaker or "").strip() or str(
            getattr(job_config, "transform_speaker", "") or ""
        )

        enabled = bool(getattr(flags, "scene_transform", False)) or bool(instr)

        try:
            pack = build_transform_intent_pack(
                enabled=enabled,
                instruction=instr,
                target_scene=scene_hint,
                target_speaker=speaker_hint,
                config=job_config,
                scenes=scenes if isinstance(scenes, dict) else None,
                speakers=speakers if isinstance(speakers, dict) else None,
                transcript=(
                    speech_transcript
                    if isinstance(speech_transcript, dict)
                    else transcript if isinstance(transcript, dict) else None
                ),
                analyze_fn=analyze_fn or self._default_analyze,
            )
        except Exception as exc:  # noqa: BLE001
            raise TransformIntentAgentError(
                f"Transform intent planning failed: {exc}"
            ) from exc

        # Resolve window onto intent when scenes available
        if not pack.plan.skipped and isinstance(scenes, dict):
            start, end, _ = resolve_scene_window(
                scenes,
                pack.plan.intent.target_scene,
                fallback_start=pack.plan.intent.start_seconds,
                fallback_end=pack.plan.intent.end_seconds,
            )
            if end > start:
                pack.plan.intent.start_seconds = start
                pack.plan.intent.end_seconds = end
            if pack.plan.intent.scenes_total <= 0:
                items = scenes.get("scenes") or scenes.get("cuts") or []
                if isinstance(items, list):
                    pack.plan.intent.scenes_total = len(items)

        path = self._write_pack(project_id, root, pack)
        public = TransformIntentResult(
            transform_intent_pack=pack, transform_intent_path=str(path)
        ).public_output()
        messages = [
            f"[{self.name}] {pack.plan.notes or pack.notes}",
            f"[{self.name}] Wrote analysis/transform_intent.json",
        ]
        if not pack.plan.skipped:
            messages.append(
                f"[{self.name}] {public.get('changed_summary')} · "
                f"preserved={public.get('scenes_preserved')}"
            )
            if public.get("unsupported_changes"):
                messages.append(
                    f"[{self.name}] Unsupported: {public.get('unsupported_changes')}"
                )
        logger.info(
            "TransformIntentAgent project_id=%s skipped=%s provider=%s",
            project_id,
            pack.plan.skipped,
            pack.plan.provider,
        )
        return TransformIntentResult(
            transform_intent_pack=pack,
            transform_intent_path=str(path),
            messages=messages,
        )

    def _default_analyze(self, **kwargs: Any) -> GeminiTransformBatch:
        """Call Gemini with structured output; raise to trigger heuristic fallback."""
        from tools.llm.gemini import analyze_transform_intent

        instruction = str(kwargs.get("instruction") or "")
        scenes = kwargs.get("scenes")
        speakers = kwargs.get("speakers")
        transcript = kwargs.get("transcript")

        scenes_block = ""
        if isinstance(scenes, dict):
            scenes_block = json.dumps(scenes, ensure_ascii=False)[:4000]
        speakers_block = ""
        if isinstance(speakers, dict):
            speakers_block = json.dumps(speakers, ensure_ascii=False)[:2000]
        transcript_block = ""
        if isinstance(transcript, dict):
            transcript_block = json.dumps(transcript, ensure_ascii=False)[:3000]

        return analyze_transform_intent(
            instruction=instruction,
            target_scene=str(kwargs.get("target_scene") or ""),
            target_speaker=str(kwargs.get("target_speaker") or ""),
            scenes_block=scenes_block,
            speakers_block=speakers_block,
            transcript_block=transcript_block,
        )

    def _coerce_project(
        self, project: ProjectMetadata | dict[str, Any]
    ) -> ProjectMetadata:
        if isinstance(project, ProjectMetadata):
            return project
        try:
            return ProjectMetadata.model_validate(project)
        except Exception as exc:  # noqa: BLE001
            raise TransformIntentAgentError(f"Invalid project metadata: {exc}") from exc

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
            raise TransformIntentAgentError(f"Invalid job config: {exc}") from exc

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
            raise TransformIntentAgentError(f"Invalid feature flags: {exc}") from exc

    def _write_pack(
        self,
        project_id: str,
        root: Path,
        pack: TransformIntentPack,
    ) -> Path:
        path = root / "analysis" / "transform_intent.json"
        try:
            try:
                canonical = get_transform_intent_path(project_id)
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
                json.dumps(pack.model_dump(mode="json"), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            raise StorageError(f"Failed to write transform intent: {path}") from exc
        return path
