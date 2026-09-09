"""Quality Agent — validate final media; correct once; fail clearly."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agents.base import BaseAgent
from core.errors import QualityAgentError, StorageError
from core.logging import get_logger
from core.paths import (
    ensure_project_analysis_dir,
    ensure_project_dir,
    get_quality_report_path,
)
from schemas.job import FeatureFlags, VideoJobConfig
from schemas.project import ProjectMetadata
from schemas.quality import QualityPack, QualityReport, QualityResult
from tools.quality.checks import attempt_corrections, run_quality_checks

logger = get_logger(__name__)


class QualityAgent(BaseAgent):
    """Validate renders/final.mp4; auto-correct once; request re-render at most once."""

    name = "quality"

    def run(
        self,
        project: ProjectMetadata | dict[str, Any],
        *,
        project_dir: str | Path | None = None,
        config: VideoJobConfig | dict[str, Any] | None = None,
        features: FeatureFlags | dict[str, Any] | None = None,
        render_pack: dict[str, Any] | None = None,
        platform_pack: dict[str, Any] | None = None,
        captions_pack: dict[str, Any] | None = None,
        quality_retry_count: int = 0,
        **_: Any,
    ) -> QualityResult:
        _ = config, features
        meta = self._coerce_project(project)
        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)

        media_path, expect_w, expect_h, expect_aspect, skipped_render, had_source = (
            self._resolve_expectations(root, render_pack, platform_pack)
        )
        caption_paths = self._caption_paths(captions_pack)

        # Soft path: only when there was never source media (script-only honesty).
        # Encode failures / missing FFmpeg with source present must fail closed.
        if skipped_render and not had_source:
            report = QualityReport(
                project_id=project_id,
                media_path=str(media_path or ""),
                checks=run_quality_checks(
                    None, require_media=False, caption_paths=caption_paths
                ),
                passed=True,
                skipped=True,
                notes="Quality soft-skipped — no rendered media (script-only honesty).",
            )
            pack = QualityPack(report=report, notes=report.notes)
            path = self._write_pack(project_id, root, pack)
            return QualityResult(
                quality_pack=pack,
                quality_path=str(path),
                messages=[
                    f"[{self.name}] Soft-skipped (no media).",
                    f"[{self.name}] Wrote analysis/quality_report.json",
                ],
            )

        # Source was expected but no deliverable: soft-skip encode OR post-encode
        # validate_video failure (skipped=False, encoded=False). Never soft-pass.
        if had_source and not media_path:
            checks = run_quality_checks(None, require_media=True, caption_paths=caption_paths)
            report = QualityReport(
                project_id=project_id,
                media_path="",
                checks=checks,
                passed=False,
                skipped=False,
                notes=(
                    "Full video generation failed. Stage: Render. "
                    "Reason: encode or validation failed with source media present."
                ),
            )
            pack = QualityPack(report=report, notes=report.notes)
            path = self._write_pack(project_id, root, pack)
            raise QualityAgentError(report.notes)

        media = Path(media_path) if media_path else Path("")
        checks = run_quality_checks(
            media,
            expect_width=expect_w,
            expect_height=expect_h,
            expect_aspect=expect_aspect,
            caption_paths=caption_paths,
            require_media=True,
        )
        corrections: list[str] = []
        passed = all(c.passed for c in checks)
        rerender = False


        notes = "All quality checks passed." if passed else "Quality checks failed."

        if not passed:
            corr_out = root / "renders" / "final_corrected.mp4"
            fixed, corrections = attempt_corrections(
                media,
                checks,
                out_path=corr_out,
                expect_width=expect_w,
                expect_height=expect_h,
            )
            if fixed is not None and fixed.is_file():
                # Replace final.mp4 when possible
                final = root / "renders" / "final.mp4"
                try:
                    if fixed.resolve() != final.resolve():
                        final.write_bytes(fixed.read_bytes())
                    media = final if final.is_file() else fixed
                    media_path = str(media)
                except OSError:
                    media = fixed
                    media_path = str(fixed)
                checks = run_quality_checks(
                    media,
                    expect_width=expect_w,
                    expect_height=expect_h,
                    expect_aspect=expect_aspect,
                    caption_paths=caption_paths,
                    require_media=True,
                )
                passed = all(c.passed for c in checks)
                notes = (
                    "Passed after automatic corrections."
                    if passed
                    else "Still failing after corrections."
                )

            if not passed:
                if int(quality_retry_count or 0) < 1:
                    rerender = True
                    notes = (
                        "Requesting single re-render after failed quality checks: "
                        + self._summary(checks)
                    )
                else:
                    summary = self._summary(checks)
                    report = QualityReport(
                        project_id=project_id,
                        media_path=str(media_path),
                        checks=checks,
                        passed=False,
                        corrections_attempted=corrections,
                        rerender_requested=False,
                        skipped=False,
                        notes=f"Quality failed after retry: {summary}",
                    )
                    pack = QualityPack(report=report, notes=report.notes)
                    self._write_pack(project_id, root, pack)
                    raise QualityAgentError(
                        f"Quality validation failed after correction/retry: {summary}"
                    )

        report = QualityReport(
            project_id=project_id,
            media_path=str(media_path or ""),
            checks=checks,
            passed=passed,
            corrections_attempted=corrections,
            rerender_requested=rerender,
            skipped=False,
            notes=notes,
        )
        pack = QualityPack(report=report, notes=notes)
        path = self._write_pack(project_id, root, pack)
        messages = [
            f"[{self.name}] passed={passed} checks={len(checks)} "
            f"corrections={corrections} rerender={rerender}",
            f"[{self.name}] Wrote analysis/quality_report.json",
        ]
        logger.info(
            "QualityAgent project_id=%s passed=%s rerender=%s",
            project_id,
            passed,
            rerender,
        )
        return QualityResult(
            quality_pack=pack, quality_path=str(path), messages=messages
        )

    def _resolve_expectations(
        self,
        root: Path,
        render_pack: dict[str, Any] | None,
        platform_pack: dict[str, Any] | None,
    ) -> tuple[str | None, int, int, str, bool, bool]:
        media_path: str | None = None
        expect_w, expect_h = 0, 0
        aspect = ""
        skipped = False
        had_source = False
        if isinstance(render_pack, dict):
            plan = render_pack.get("plan") or {}
            if isinstance(plan, dict):
                skipped = bool(plan.get("skipped")) and not bool(plan.get("encoded"))
                src = str(plan.get("source_path") or "").strip()
                # Recorded plan path only — do not require the file on disk
                # (moved/deleted/restored projects must still fail closed).
                had_source = bool(src)
                op = str(plan.get("output_path") or "").strip()
                if op and Path(op).is_file():
                    media_path = op
                try:
                    expect_w = int(plan.get("target_width") or 0)
                    expect_h = int(plan.get("target_height") or 0)
                except (TypeError, ValueError):
                    pass
                aspect = str(plan.get("target_aspect") or "")
        if media_path is None:
            cand = root / "renders" / "final.mp4"
            if cand.is_file():
                media_path = str(cand)
            else:
                packaged = root / "final" / "final.mp4"
                if packaged.is_file():
                    media_path = str(packaged)
        if not aspect and isinstance(platform_pack, dict):
            pplan = platform_pack.get("plan") or {}
            if isinstance(pplan, dict):
                meta = pplan.get("metadata") or {}
                hints = pplan.get("export_hints") or {}
                if isinstance(meta, dict):
                    aspect = str(meta.get("aspect_recommendation") or "")
                if isinstance(hints, dict) and hints.get("preferred_aspect"):
                    aspect = str(hints["preferred_aspect"])
        return media_path, expect_w, expect_h, aspect, skipped, had_source

    def _caption_paths(self, captions_pack: dict[str, Any] | None) -> list[str]:
        paths: list[str] = []
        if not isinstance(captions_pack, dict):
            return paths
        for key in ("srt_path", "vtt_path", "ass_path"):
            p = str(captions_pack.get(key) or "").strip()
            if p and Path(p).is_file():
                paths.append(p)
        return paths

    def _summary(self, checks: list[Any]) -> str:
        failed = [c for c in checks if not getattr(c, "passed", True)]
        parts = [
            f"{c.id}: {c.message or c.actual}" for c in failed[:8]
        ]
        return "; ".join(parts) if parts else "unknown"

    def _coerce_project(
        self, project: ProjectMetadata | dict[str, Any]
    ) -> ProjectMetadata:
        if isinstance(project, ProjectMetadata):
            return project
        try:
            return ProjectMetadata.model_validate(project)
        except Exception as exc:  # noqa: BLE001
            raise QualityAgentError(f"Invalid project metadata: {exc}") from exc

    def _write_pack(
        self, project_id: str, root: Path, pack: QualityPack
    ) -> Path:
        try:
            ensure_project_analysis_dir(project_id)
        except Exception:  # noqa: BLE001
            pass
        path = root / "analysis" / "quality_report.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_text(
                json.dumps(pack.model_dump(mode="json"), indent=2),
                encoding="utf-8",
            )
            try:
                alt = get_quality_report_path(project_id)
                if alt.resolve() != path.resolve():
                    alt.parent.mkdir(parents=True, exist_ok=True)
                    alt.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            except Exception:  # noqa: BLE001
                pass
        except OSError as exc:
            raise StorageError(f"Failed to write quality report: {exc}") from exc
        return path
