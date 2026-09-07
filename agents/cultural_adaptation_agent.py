"""Cultural Adaptation Agent — analyze scripts for cultural localization metadata."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from agents.base import BaseAgent
from core.errors import CulturalAdaptationError, StorageError
from core.logging import get_logger
from core.paths import (
    ensure_project_analysis_dir,
    ensure_project_dir,
    get_cultural_adaptation_path,
    get_locale_context_path,
)
from schemas.job import FeatureFlags, VideoJobConfig
from schemas.localization import (
    CulturalAdaptationReport,
    CulturalAdaptationResult,
    CulturalFinding,
    GeminiCulturalBatch,
    LocalePack,
    LocalizationTarget,
)
from schemas.project import ProjectMetadata
from schemas.story import ClipScript, ScriptsReport
from tools.localization.catalog import locale_pack_prompt_block

logger = get_logger(__name__)

AnalyzeFn = Callable[..., GeminiCulturalBatch]


class CulturalAdaptationAgent(BaseAgent):
    """Write analysis/cultural_adaptation.json and enrich locale_pack."""

    name = "cultural"

    def __init__(self, analyze_fn: AnalyzeFn | None = None) -> None:
        self._analyze_fn = analyze_fn

    def run(
        self,
        project: ProjectMetadata | dict[str, Any],
        *,
        project_dir: str | Path | None = None,
        config: VideoJobConfig | dict[str, Any] | None = None,
        features: FeatureFlags | dict[str, Any] | None = None,
        scripts: dict[str, Any] | ScriptsReport | None = None,
        locale_pack: dict[str, Any] | LocalePack | None = None,
        **_: Any,
    ) -> CulturalAdaptationResult:
        meta = self._coerce_project(project)
        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)
        job_config = self._coerce_config(config)
        flags = self._coerce_features(features)
        script_list = self._parse_scripts(scripts)
        pack = self._coerce_locale_pack(locale_pack, job_config)
        pack.audience = job_config.audience

        target = LocalizationTarget(
            country=job_config.country,
            region=job_config.region if pack.region else "",
            language=job_config.language,
        )
        if pack.target.country:
            target = pack.target

        if not flags.cultural_adaptation or not script_list:
            notes = (
                "Cultural adaptation skipped (flag off or no scripts)."
                if not flags.cultural_adaptation
                else "No scripts — cultural adaptation skipped."
            )
            report = CulturalAdaptationReport(
                project_id=project_id,
                audience=job_config.audience,
                target=target,
                findings=[],
                provider="skipped",
                notes=notes,
                cultural_summary="",
            )
            pack.cultural_summary = ""
            path = self._write_report(project_id, root, report)
            self._update_locale_context(project_id, root, pack, report)
            return CulturalAdaptationResult(
                cultural_adaptation=report,
                cultural_adaptation_path=str(path),
                locale_pack=pack,
                messages=[f"[{self.name}] {notes}"],
            )

        script_blocks = [self._format_script(s) for s in script_list]
        locale_block = locale_pack_prompt_block(pack)
        try:
            from tools.llm.gemini import analyze_cultural_adaptation

            analyze = self._analyze_fn or analyze_cultural_adaptation
            batch = analyze(
                script_blocks,
                locale_block=locale_block,
                audience=job_config.audience,
            )
        except CulturalAdaptationError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise CulturalAdaptationError(
                f"Cultural adaptation failed: {exc}"
            ) from exc

        if not isinstance(batch, GeminiCulturalBatch):
            batch = GeminiCulturalBatch.model_validate(batch)

        findings = [
            CulturalFinding(
                clip_id=f.clip_id,
                kind=f.kind or "reference",
                source_span=(f.source_span or "").strip(),
                risk=(f.risk or "").strip(),
                recommendation=(f.recommendation or "").strip(),
                local_equivalent=(f.local_equivalent or "").strip(),
            )
            for f in batch.findings
        ]
        summary = (batch.cultural_summary or "").strip()
        if not summary and findings:
            summary = "; ".join(
                f.recommendation for f in findings[:5] if f.recommendation
            )

        pack.cultural_summary = summary
        if summary and summary not in pack.summary_notes:
            pack.summary_notes = list(pack.summary_notes) + [f"Cultural: {summary}"]

        report = CulturalAdaptationReport(
            project_id=project_id,
            audience=job_config.audience,
            target=target,
            findings=findings,
            provider="gemini-cultural",
            notes=f"Analyzed {len(script_list)} script(s); {len(findings)} finding(s).",
            cultural_summary=summary,
        )
        path = self._write_report(project_id, root, report)
        self._update_locale_context(project_id, root, pack, report)
        messages = [
            f"[{self.name}] Findings: {len(findings)}",
            f"[{self.name}] Wrote analysis/cultural_adaptation.json",
        ]
        logger.info(
            "CulturalAdaptation ready project_id=%s findings=%s",
            project_id,
            len(findings),
        )
        return CulturalAdaptationResult(
            cultural_adaptation=report,
            cultural_adaptation_path=str(path),
            locale_pack=pack,
            messages=messages,
        )

    def _format_script(self, script: ClipScript) -> str:
        return (
            f"### clip_id={script.clip_id}\n"
            f"title: {script.title}\n"
            f"hook: {script.hook}\n"
            f"short_script: {script.short_script}\n"
            f"caption: {script.caption}\n"
            f"cta: {script.cta}"
        )

    def _parse_scripts(
        self, scripts: dict[str, Any] | ScriptsReport | None
    ) -> list[ClipScript]:
        if scripts is None:
            return []
        if isinstance(scripts, ScriptsReport):
            return list(scripts.scripts)
        try:
            return list(ScriptsReport.model_validate(scripts).scripts)
        except Exception:
            raw = scripts.get("scripts") if isinstance(scripts, dict) else None
            if not isinstance(raw, list):
                return []
            out: list[ClipScript] = []
            for item in raw:
                try:
                    out.append(
                        item
                        if isinstance(item, ClipScript)
                        else ClipScript.model_validate(item)
                    )
                except Exception:  # noqa: BLE001
                    continue
            return out

    def _coerce_locale_pack(
        self,
        locale_pack: dict[str, Any] | LocalePack | None,
        config: VideoJobConfig,
    ) -> LocalePack:
        if isinstance(locale_pack, LocalePack):
            return locale_pack.model_copy(deep=True)
        if isinstance(locale_pack, dict) and locale_pack:
            try:
                return LocalePack.model_validate(locale_pack)
            except Exception:  # noqa: BLE001
                pass
        from tools.localization.catalog import build_locale_pack

        return build_locale_pack(
            LocalizationTarget(
                country=config.country,
                region=config.region,
                language=config.language,
            ),
            voice=config.voice,
        )

    def _coerce_project(self, project: ProjectMetadata | dict[str, Any]) -> ProjectMetadata:
        if isinstance(project, ProjectMetadata):
            return project
        try:
            return ProjectMetadata.model_validate(project)
        except Exception as exc:  # noqa: BLE001
            raise CulturalAdaptationError(f"Invalid project metadata: {exc}") from exc

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
            raise CulturalAdaptationError(f"Invalid job config: {exc}") from exc

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
            raise CulturalAdaptationError(f"Invalid feature flags: {exc}") from exc

    def _write_report(
        self,
        project_id: str,
        root: Path,
        report: CulturalAdaptationReport,
    ) -> Path:
        path = root / "analysis" / "cultural_adaptation.json"
        try:
            try:
                canonical = get_cultural_adaptation_path(project_id)
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
            raise StorageError(
                f"Failed to write cultural_adaptation.json: {path}"
            ) from exc
        return path.resolve()

    def _update_locale_context(
        self,
        project_id: str,
        root: Path,
        pack: LocalePack,
        report: CulturalAdaptationReport,
    ) -> None:
        path = root / "analysis" / "locale_context.json"
        try:
            try:
                canonical = get_locale_context_path(project_id)
                if canonical.parent.parent == root.resolve():
                    path = canonical
            except Exception:  # noqa: BLE001
                pass
            existing: dict[str, Any] = {}
            if path.is_file():
                try:
                    existing = json.loads(path.read_text(encoding="utf-8"))
                except Exception:  # noqa: BLE001
                    existing = {}
            existing["locale_pack"] = pack.model_dump(mode="json")
            existing["cultural_adaptation"] = report.model_dump(mode="json")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        except OSError:
            logger.warning("Could not update locale_context.json for cultural agent")
