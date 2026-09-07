"""Smart Reframe Agent — OpenCV focus plan first, then optional FFmpeg encode."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agents.base import BaseAgent
from core.errors import ReframeAgentError, StorageError
from core.logging import get_logger
from core.paths import (
    ensure_project_analysis_dir,
    ensure_project_dir,
    ensure_project_renders_dir,
    get_reframe_plan_path,
)
from schemas.job import FeatureFlags, VideoJobConfig
from schemas.project import ProjectMetadata
from schemas.reframe import ReframePack, ReframeResult
from tools.reframe.catalog import resolve_target_aspect
from tools.reframe.detect import detect_focus_samples
from tools.reframe.plan import build_reframe_plan
from tools.reframe.render import render_reframe
from tools.video.probe import probe_video_properties

logger = get_logger(__name__)


class ReframeAgent(BaseAgent):
    """Write analysis/reframe_plan.json; encode renders/reframed.mp4 when possible."""

    name = "smart_reframe"

    def run(
        self,
        project: ProjectMetadata | dict[str, Any],
        *,
        project_dir: str | Path | None = None,
        config: VideoJobConfig | dict[str, Any] | None = None,
        features: FeatureFlags | dict[str, Any] | None = None,
        clips: dict[str, Any] | None = None,
        analysis: dict[str, Any] | None = None,
        speakers: dict[str, Any] | None = None,
        video_type_pack: dict[str, Any] | None = None,
        source_metadata: dict[str, Any] | None = None,
        speech_transcript: dict[str, Any] | None = None,
        **_: Any,
    ) -> ReframeResult:
        meta = self._coerce_project(project)
        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)
        job_config = self._coerce_config(config)
        flags = self._coerce_features(features)

        vt_aspect = ""
        if isinstance(video_type_pack, dict):
            preset = video_type_pack.get("preset") or {}
            if isinstance(preset, dict):
                vt_aspect = str(preset.get("aspect_ratio") or "")

        aspect = resolve_target_aspect(
            reframe_aspect=getattr(job_config, "reframe_aspect", "") or "",
            video_type_aspect=vt_aspect,
            platform=job_config.platform,
        )

        media = self._resolve_media_path(meta, source_metadata, speech_transcript)
        notes_parts: list[str] = []

        if not flags.smart_reframing:
            plan = build_reframe_plan(
                project_id=project_id,
                src_w=0,
                src_h=0,
                duration=0.0,
                aspect=aspect,
                samples=[],
                clips=None,
                skipped=True,
                notes="Smart reframing feature flag off — skipped.",
            )
            pack = ReframePack(plan=plan, aspect=aspect, notes=plan.notes)
            path = self._write_pack(project_id, root, pack)
            return ReframeResult(
                reframe_pack=pack,
                reframe_path=str(path),
                messages=[
                    f"[{self.name}] Smart reframing skipped (feature flag off).",
                    f"[{self.name}] Wrote analysis/reframe_plan.json",
                ],
            )

        src_w, src_h, duration = 0, 0, 0.0
        samples = []
        if media is not None:
            try:
                props = probe_video_properties(media)
                src_w, src_h = props.width, props.height
                duration = props.duration_seconds
            except Exception as exc:  # noqa: BLE001
                notes_parts.append(f"Probe failed: {exc}")
            try:
                from tools.vision.face_gate import should_run_face_detection

                face_on = should_run_face_detection(
                    video_type_pack=video_type_pack
                    if isinstance(video_type_pack, dict)
                    else None,
                    config_video_type=getattr(job_config, "video_type", None),
                )
                if not face_on:
                    notes_parts.append(
                        "Face detection skipped (video type gate)."
                    )
                samples = detect_focus_samples(
                    media,
                    analysis=analysis,
                    speakers=speakers,
                    start=0.0,
                    end=duration if duration > 0 else None,
                    enable_face=face_on,
                )
                notes_parts.append(f"Collected {len(samples)} focus sample(s).")
            except Exception as exc:  # noqa: BLE001
                notes_parts.append(f"Detection soft-failed: {exc}")
                samples = []
        else:
            notes_parts.append("No media path — plan only (no encode).")
            # Use analysis dimensions if present
            if isinstance(analysis, dict):
                props = analysis.get("properties") or {}
                if isinstance(props, dict):
                    try:
                        src_w = int(props.get("width") or 0)
                        src_h = int(props.get("height") or 0)
                        duration = float(props.get("duration_seconds") or 0.0)
                    except (TypeError, ValueError):
                        pass

        if src_w <= 0 or src_h <= 0:
            src_w, src_h = 1920, 1080
            notes_parts.append(
                "Using placeholder 1920x1080 for plan geometry (no probed size)."
            )

        plan = build_reframe_plan(
            project_id=project_id,
            src_w=src_w,
            src_h=src_h,
            duration=duration,
            aspect=aspect,
            samples=samples,
            clips=clips,
            skipped=False,
            notes=" ".join(notes_parts) or "Reframe plan built.",
        )
        pack = ReframePack(plan=plan, aspect=aspect, notes=plan.notes)

        # Always write plan first (before encode)
        path = self._write_pack(project_id, root, pack)
        messages = [
            f"[{self.name}] Plan written target={aspect.name} "
            f"passthrough={plan.passthrough} windows="
            f"{sum(len(c.windows) for c in plan.clip_plans)}",
            f"[{self.name}] Wrote analysis/reframe_plan.json",
        ]

        encoded_path = ""
        if media is not None and plan.clip_plans:
            renders = root / "renders"
            renders.mkdir(parents=True, exist_ok=True)
            try:
                ensure_project_renders_dir(project_id)
            except Exception:  # noqa: BLE001
                pass
            out = renders / "reframed.mp4"
            try:
                from tools.ffmpeg.async_runner import run_in_ffmpeg_pool

                try:
                    result_path = run_in_ffmpeg_pool(render_reframe, media, plan, out)
                except Exception:
                    result_path = render_reframe(media, plan, out)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Reframe encode error: %s", exc)
                result_path = None
            if result_path is not None and result_path.is_file():
                encoded_path = str(result_path)
                pack.plan.encoded = True
                pack.plan.output_path = encoded_path
                notes_parts.append("Encoded reframed.mp4")
                messages.append(f"[{self.name}] Encoded {encoded_path}")
            else:
                pack.plan.encoded = False
                pack.plan.output_path = ""
                notes_parts.append(
                    "Encode soft-skipped (FFmpeg unavailable or encode failed)."
                )
                messages.append(f"[{self.name}] Encode soft-skipped.")
            pack.plan.notes = " ".join(notes_parts)
            pack.notes = pack.plan.notes
            # Re-write pack with encode status
            path = self._write_pack(project_id, root, pack)
        else:
            pack.plan.encoded = False
            messages.append(f"[{self.name}] Encode skipped (no media or empty plan).")

        # Honesty: never claim encoded without file
        if pack.plan.encoded and not (pack.plan.output_path or "").strip():
            pack.plan.encoded = False
            path = self._write_pack(project_id, root, pack)

        logger.info(
            "ReframeAgent ready project_id=%s target=%s encoded=%s",
            project_id,
            aspect.name,
            pack.plan.encoded,
        )
        return ReframeResult(
            reframe_pack=pack, reframe_path=str(path), messages=messages
        )

    def _coerce_project(
        self, project: ProjectMetadata | dict[str, Any]
    ) -> ProjectMetadata:
        if isinstance(project, ProjectMetadata):
            return project
        try:
            return ProjectMetadata.model_validate(project)
        except Exception as exc:  # noqa: BLE001
            raise ReframeAgentError(f"Invalid project metadata: {exc}") from exc

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
            raise ReframeAgentError(f"Invalid job config: {exc}") from exc

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
            raise ReframeAgentError(f"Invalid feature flags: {exc}") from exc

    def _resolve_media_path(
        self,
        meta: ProjectMetadata,
        source_metadata: dict[str, Any] | None,
        speech_transcript: dict[str, Any] | None,
    ) -> Path | None:
        candidates: list[str] = []
        if isinstance(speech_transcript, dict):
            mp = speech_transcript.get("media_path")
            if mp:
                candidates.append(str(mp))
        if isinstance(source_metadata, dict):
            for key in ("media_path", "local_path", "video_path", "path"):
                val = source_metadata.get(key)
                if val:
                    candidates.append(str(val))
        if meta.source_path:
            candidates.append(str(meta.source_path))
        for raw in candidates:
            path = Path(raw)
            if path.is_file():
                return path
        return None

    def _write_pack(
        self,
        project_id: str,
        root: Path,
        pack: ReframePack,
    ) -> Path:
        path = root / "analysis" / "reframe_plan.json"
        try:
            try:
                canonical = get_reframe_plan_path(project_id)
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
            raise StorageError(f"Failed to write reframe_plan.json: {path}") from exc
        return path.resolve()
