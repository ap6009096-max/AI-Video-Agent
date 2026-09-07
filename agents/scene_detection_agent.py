"""Scene Detection Agent — fused visual + speaker boundaries → scenes.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from agents.base import BaseAgent
from core.errors import SceneDetectionError, StorageError
from core.logging import get_logger
from core.paths import ensure_project_analysis_dir, ensure_project_dir, get_scenes_path
from schemas.project import ProjectMetadata
from schemas.scenes import DetectedScene, SceneDetectionReport, SceneDetectionResult

logger = get_logger(__name__)

DetectFn = Callable[..., dict[str, Any]]


class SceneDetectionAgent(BaseAgent):
    """Authoritative scene list for Smart Clip Agent (signals only, not clips)."""

    name = "scene_detection"

    def __init__(self, detect_fn: DetectFn | None = None) -> None:
        self._detect_fn = detect_fn

    def run(
        self,
        project: ProjectMetadata | dict[str, Any],
        *,
        project_dir: str | Path | None = None,
        source_metadata: dict[str, Any] | None = None,
        analysis: dict[str, Any] | None = None,
        speech_transcript: dict[str, Any] | None = None,
        transcript: dict[str, Any] | None = None,
        **_: Any,
    ) -> SceneDetectionResult:
        meta = self._coerce_project(project)
        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)

        media_path = self._resolve_media_path(meta, source_metadata)
        try:
            from tools.video.scene_detect import detect_scenes

            detect = self._detect_fn or detect_scenes
            result = detect(
                media_path=media_path,
                analysis=analysis,
                speech_transcript=speech_transcript,
                transcript=transcript,
            )
        except SceneDetectionError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise SceneDetectionError(f"Scene detection failed: {exc}") from exc

        scenes_raw = result.get("scenes") or []
        scenes: list[DetectedScene] = []
        for item in scenes_raw:
            if isinstance(item, DetectedScene):
                scenes.append(item)
            else:
                scenes.append(DetectedScene.model_validate(item))

        notes = str(result.get("notes") or "")
        provider = "opencv-ffmpeg"
        if not media_path:
            provider = "transcript-only"
            notes = notes or (
                "Transcript-only scene detection: no local video. "
                "Visual/OpenCV rescan skipped; speaker/section gaps used when available."
            )
        elif not (analysis or {}).get("visual_changes") and not (result.get("source_signals") or {}).get(
            "rescanned"
        ):
            if not notes:
                notes = "Scenes fused from analysis and/or transcript signals."

        report = SceneDetectionReport(
            project_id=project_id,
            media_path=str(Path(media_path).resolve()) if media_path else "",
            scenes=scenes,
            provider=provider,
            notes=notes,
            source_signals=dict(result.get("source_signals") or {}),
        )
        path = self._write_report(project_id, root, report)
        messages = [
            f"[{self.name}] Scenes: {len(scenes)}",
            f"[{self.name}] Provider: {provider}",
            f"[{self.name}] Wrote analysis/scenes.json",
        ]
        logger.info(
            "SceneDetection ready project_id=%s scenes=%s provider=%s",
            project_id,
            len(scenes),
            provider,
        )
        return SceneDetectionResult(
            scenes=report, scenes_path=str(path), messages=messages
        )

    def _coerce_project(self, project: ProjectMetadata | dict[str, Any]) -> ProjectMetadata:
        if isinstance(project, ProjectMetadata):
            return project
        try:
            return ProjectMetadata.model_validate(project)
        except Exception as exc:  # noqa: BLE001
            raise SceneDetectionError(f"Invalid project metadata: {exc}") from exc

    def _resolve_media_path(
        self,
        meta: ProjectMetadata,
        source_metadata: dict[str, Any] | None,
    ) -> str | None:
        candidates: list[str] = []
        if meta.source_path:
            candidates.append(meta.source_path)
        if source_metadata and source_metadata.get("local_media_path"):
            candidates.append(str(source_metadata["local_media_path"]))
        for path in candidates:
            if path and Path(path).is_file():
                return path
        return None

    def _write_report(
        self,
        project_id: str,
        root: Path,
        report: SceneDetectionReport,
    ) -> Path:
        path = root / "analysis" / "scenes.json"
        try:
            try:
                canonical = get_scenes_path(project_id)
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
                json.dumps(report.model_dump(mode="json"), indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            raise StorageError(f"Failed to write scenes.json: {path}") from exc
        return path.resolve()
