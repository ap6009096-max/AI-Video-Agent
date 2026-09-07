"""Export Agent — package deliverables into exports/ (no Gemini)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from agents.base import BaseAgent
from core.errors import ExportAgentError, StorageError
from core.logging import get_logger
from core.paths import (
    ensure_project_dir,
    ensure_project_exports_dir,
    get_export_manifest_path,
)
from schemas.export_bundle import ExportBundle, ExportPack, ExportResult
from schemas.job import FeatureFlags, VideoJobConfig
from schemas.project import ProjectMetadata
from tools.project.layout import finalize_project_layout

logger = get_logger(__name__)


class ExportAgent(BaseAgent):
    """Copy final assets into exports/ and write manifest.json."""

    name = "export"

    def run(
        self,
        project: ProjectMetadata | dict[str, Any],
        *,
        project_dir: str | Path | None = None,
        config: VideoJobConfig | dict[str, Any] | None = None,
        features: FeatureFlags | dict[str, Any] | None = None,
        render_pack: dict[str, Any] | None = None,
        quality_pack: dict[str, Any] | None = None,
        captions_pack: dict[str, Any] | None = None,
        platform_pack: dict[str, Any] | None = None,
        workflow_state: dict[str, Any] | None = None,
        **_: Any,
    ) -> ExportResult:
        _ = config, features
        meta = self._coerce_project(project)
        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)
        exports = root / "exports"
        exports.mkdir(parents=True, exist_ok=True)
        try:
            ensure_project_exports_dir(project_id)
        except Exception:  # noqa: BLE001
            pass

        # Never claim success when quality failed
        if isinstance(quality_pack, dict):
            report = quality_pack.get("report") or {}
            if isinstance(report, dict) and report.get("passed") is False and not report.get(
                "skipped"
            ):
                raise ExportAgentError(
                    "Refusing export: quality report passed=False — "
                    "will not ship broken media."
                )

        video_src = self._video_src(root, render_pack)
        thumb_src = self._thumb_src(root, render_pack)
        caption_srcs = self._caption_srcs(captions_pack)
        platform_meta = self._platform_meta(root, platform_pack)

        quality_skipped = False
        if isinstance(quality_pack, dict):
            report = quality_pack.get("report") or {}
            if isinstance(report, dict):
                quality_skipped = bool(report.get("skipped"))

        render_skipped = False
        if isinstance(render_pack, dict):
            plan = render_pack.get("plan") or {}
            if isinstance(plan, dict):
                render_skipped = bool(plan.get("skipped")) and not bool(
                    plan.get("encoded")
                )

        video_dst = ""
        thumb_dst = ""
        caption_dsts: list[str] = []
        platform_dst = ""

        if video_src is not None:
            dest = exports / video_src.name
            self._safe_copy(video_src, dest)
            if dest.is_file():
                video_dst = str(dest)

        if thumb_src is not None:
            dest = exports / thumb_src.name
            self._safe_copy(thumb_src, dest)
            if dest.is_file():
                thumb_dst = str(dest)

        for src in caption_srcs:
            dest = exports / src.name
            self._safe_copy(src, dest)
            if dest.is_file():
                caption_dsts.append(str(dest))

        if platform_meta is not None:
            dest = exports / "platform_metadata.json"
            if platform_meta.resolve() != dest.resolve():
                self._safe_copy(platform_meta, dest)
            if dest.is_file():
                platform_dst = str(dest)

        # Copy multi Shorts MP4s into exports/
        short_export_paths: list[str] = []
        shorts_dir = root / "renders" / "shorts"
        if shorts_dir.is_dir():
            for mp4 in sorted(shorts_dir.glob("short_*.mp4")):
                if not mp4.is_file():
                    continue
                dest = exports / mp4.name
                self._safe_copy(mp4, dest)
                if dest.is_file():
                    short_export_paths.append(str(dest))
        if isinstance(render_pack, dict):
            plan = render_pack.get("plan") or {}
            if isinstance(plan, dict):
                for sp in plan.get("short_paths") or []:
                    src = Path(str(sp))
                    if not src.is_file():
                        continue
                    dest = exports / src.name
                    self._safe_copy(src, dest)
                    if dest.is_file() and str(dest) not in short_export_paths:
                        short_export_paths.append(str(dest))

        # Dual-write PROMPT 25 layout aliases + folders
        state_for_layout = dict(workflow_state or {})
        state_for_layout.update(
            {
                "render_pack": render_pack,
                "quality_pack": quality_pack,
                "captions_pack": captions_pack,
                "platform_pack": platform_pack,
            }
        )
        output_files = finalize_project_layout(
            root,
            state=state_for_layout,
            captions_pack=captions_pack,
            render_pack=render_pack,
        )
        if short_export_paths:
            folders = dict(output_files.get("folders") or {})
            existing_shorts = list(folders.get("shorts") or [])
            for p in short_export_paths:
                if p not in existing_shorts:
                    existing_shorts.append(p)
            folders["shorts"] = existing_shorts
            output_files["folders"] = folders

        manifest_path = exports / "manifest.json"
        bundle = ExportBundle(
            video_path=video_dst,
            thumbnail_path=thumb_dst,
            caption_paths=caption_dsts,
            platform_metadata_path=platform_dst,
            manifest_path=str(manifest_path),
            notes="",
        )

        skipped = False
        notes = "Export package ready."
        if not video_dst:
            if quality_skipped or render_skipped:
                skipped = True
                notes = (
                    "No video deliverable — script-only / soft-skip path. "
                    "Manifest is the honest export artifact."
                )
            else:
                raise ExportAgentError(
                    "Export failed: final video missing and quality did not soft-skip."
                )

        export_path = video_dst or str(manifest_path)
        pack = ExportPack(
            project_id=project_id,
            bundle=bundle,
            export_path=export_path,
            skipped=skipped,
            output_files=output_files,
            notes=notes,
        )
        bundle.notes = notes
        pack.bundle = bundle

        try:
            manifest = {
                "project_id": project_id,
                "export_path": export_path,
                "skipped": skipped,
                "bundle": bundle.model_dump(mode="json"),
                "output_files": output_files,
                "notes": notes,
            }
            manifest_path.write_text(
                json.dumps(manifest, indent=2), encoding="utf-8"
            )
            try:
                alt = get_export_manifest_path(project_id)
                if alt.resolve() != manifest_path.resolve():
                    alt.parent.mkdir(parents=True, exist_ok=True)
                    alt.write_text(
                        manifest_path.read_text(encoding="utf-8"), encoding="utf-8"
                    )
            except Exception:  # noqa: BLE001
                pass
        except OSError as exc:
            raise StorageError(f"Failed to write export manifest: {exc}") from exc

        # Also write pack summary beside manifest for agents that read export_pack from state
        pack_path = exports / "export_pack.json"
        try:
            pack_path.write_text(
                json.dumps(pack.model_dump(mode="json"), indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass

        messages = [
            f"[{self.name}] {notes}",
            f"[{self.name}] Wrote exports/manifest.json",
            f"[{self.name}] Dual-wrote project layout aliases",
            f"[{self.name}] export_path={export_path}",
        ]
        logger.info(
            "ExportAgent ready project_id=%s export_path=%s skipped=%s",
            project_id,
            export_path,
            skipped,
        )
        return ExportResult(
            export_pack=pack,
            export_manifest_path=str(manifest_path),
            messages=messages,
        )

    def _video_src(
        self, root: Path, render_pack: dict[str, Any] | None
    ) -> Path | None:
        if isinstance(render_pack, dict):
            plan = render_pack.get("plan") or {}
            if isinstance(plan, dict):
                op = str(plan.get("output_path") or "").strip()
                if op and Path(op).is_file():
                    return Path(op)
        cand = root / "renders" / "final.mp4"
        return cand if cand.is_file() else None

    def _thumb_src(
        self, root: Path, render_pack: dict[str, Any] | None
    ) -> Path | None:
        if isinstance(render_pack, dict):
            plan = render_pack.get("plan") or {}
            if isinstance(plan, dict):
                tp = str(plan.get("thumbnail_path") or "").strip()
                if tp and Path(tp).is_file():
                    return Path(tp)
        cand = root / "renders" / "thumbnail.jpg"
        return cand if cand.is_file() else None

    def _caption_srcs(self, captions_pack: dict[str, Any] | None) -> list[Path]:
        out: list[Path] = []
        if not isinstance(captions_pack, dict):
            return out
        for key in ("srt_path", "vtt_path", "ass_path"):
            p = str(captions_pack.get(key) or "").strip()
            if p and Path(p).is_file():
                out.append(Path(p))
        return out

    def _platform_meta(
        self, root: Path, platform_pack: dict[str, Any] | None
    ) -> Path | None:
        if isinstance(platform_pack, dict):
            ep = str(platform_pack.get("export_path") or "").strip()
            if ep and Path(ep).is_file():
                return Path(ep)
        cand = root / "exports" / "platform_metadata.json"
        return cand if cand.is_file() else None

    def _safe_copy(self, src: Path, dst: Path) -> None:
        try:
            if src.resolve() == dst.resolve():
                return
            shutil.copy2(src, dst)
        except OSError as exc:
            logger.warning("Export copy failed %s -> %s: %s", src, dst, exc)

    def _coerce_project(
        self, project: ProjectMetadata | dict[str, Any]
    ) -> ProjectMetadata:
        if isinstance(project, ProjectMetadata):
            return project
        try:
            return ProjectMetadata.model_validate(project)
        except Exception as exc:  # noqa: BLE001
            raise ExportAgentError(f"Invalid project metadata: {exc}") from exc
