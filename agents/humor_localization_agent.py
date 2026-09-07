"""Humor Localization Agent — plan humor handling without forcing jokes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from agents.base import BaseAgent
from core.errors import HumorLocalizationError, StorageError
from core.logging import get_logger
from core.paths import (
    ensure_project_analysis_dir,
    ensure_project_dir,
    get_humor_localization_path,
    get_locale_context_path,
)
from schemas.job import FeatureFlags, HumorAdaptationMode, VideoJobConfig
from schemas.localization import (
    CulturalAdaptationReport,
    GeminiHumorBatch,
    HumorLocalizationReport,
    HumorLocalizationResult,
    HumorPlanItem,
    LocalePack,
    LocalizationTarget,
)
from schemas.project import ProjectMetadata
from schemas.story import ClipScript, ScriptsReport
from tools.localization.catalog import locale_pack_prompt_block

logger = get_logger(__name__)

PlanFn = Callable[..., GeminiHumorBatch]


def resolve_effective_humor_mode(
    *,
    humor_adaptation: str,
    regional_humor_flag: bool,
    has_region_profile: bool,
) -> HumorAdaptationMode:
    """Resolve effective humor mode from config + regional_humor flag."""
    mode = (humor_adaptation or "none").strip().lower()
    if mode not in ("original", "localized", "regional", "none"):
        mode = "none"

    if regional_humor_flag and mode in ("none", "localized"):
        mode = "regional"

    if mode == "regional" and not has_region_profile:
        mode = "localized"

    return mode  # type: ignore[return-value]


class HumorLocalizationAgent(BaseAgent):
    """Write analysis/humor_localization.json and enrich locale_pack."""

    name = "humor"

    def __init__(self, plan_fn: PlanFn | None = None) -> None:
        self._plan_fn = plan_fn

    def run(
        self,
        project: ProjectMetadata | dict[str, Any],
        *,
        project_dir: str | Path | None = None,
        config: VideoJobConfig | dict[str, Any] | None = None,
        features: FeatureFlags | dict[str, Any] | None = None,
        scripts: dict[str, Any] | ScriptsReport | None = None,
        locale_pack: dict[str, Any] | LocalePack | None = None,
        cultural_adaptation: dict[str, Any] | CulturalAdaptationReport | None = None,
        **_: Any,
    ) -> HumorLocalizationResult:
        meta = self._coerce_project(project)
        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)
        job_config = self._coerce_config(config)
        flags = self._coerce_features(features)
        script_list = self._parse_scripts(scripts)
        pack = self._coerce_locale_pack(locale_pack, job_config)
        cultural = self._coerce_cultural(cultural_adaptation)
        cultural_summary = (
            cultural.cultural_summary
            if cultural
            else (pack.cultural_summary or "")
        )

        effective = resolve_effective_humor_mode(
            humor_adaptation=job_config.humor_adaptation,
            regional_humor_flag=bool(flags.regional_humor),
            has_region_profile=pack.region is not None,
        )
        pack.audience = job_config.audience
        pack.humor_adaptation = effective
        pack.humor_style = job_config.humor_style
        pack.include_regional_humor = effective == "regional" or bool(
            flags.regional_humor
        )

        if not script_list:
            notes = "No scripts — humor localization skipped."
            report = HumorLocalizationReport(
                project_id=project_id,
                mode=effective,
                humor_style=job_config.humor_style,
                audience=job_config.audience,
                items=[],
                provider="skipped",
                notes=notes,
                humor_summary="",
            )
            pack.humor_summary = ""
            path = self._write_report(project_id, root, report)
            self._update_locale_context(project_id, root, pack, report)
            return HumorLocalizationResult(
                humor_localization=report,
                humor_localization_path=str(path),
                locale_pack=pack,
                messages=[f"[{self.name}] {notes}"],
            )

        # Mode none: structured keep-all metadata without Gemini joke planning
        if effective == "none":
            items = [
                HumorPlanItem(
                    clip_id=s.clip_id,
                    source_humor_present=False,
                    strategy="keep",
                    rationale="No humor adaptation requested.",
                    suggested_approach="Preserve meaning; do not rewrite for comedy.",
                )
                for s in script_list
            ]
            summary = (
                "Humor mode=none: no humor rewriting; preserve original meaning."
            )
            pack.humor_summary = summary
            report = HumorLocalizationReport(
                project_id=project_id,
                mode=effective,
                humor_style=job_config.humor_style,
                audience=job_config.audience,
                items=items,
                provider="rules",
                notes=summary,
                humor_summary=summary,
            )
            path = self._write_report(project_id, root, report)
            self._update_locale_context(project_id, root, pack, report)
            return HumorLocalizationResult(
                humor_localization=report,
                humor_localization_path=str(path),
                locale_pack=pack,
                messages=[
                    f"[{self.name}] Mode: {effective}",
                    f"[{self.name}] Wrote analysis/humor_localization.json",
                ],
            )

        script_blocks = [self._format_script(s) for s in script_list]
        locale_block = locale_pack_prompt_block(pack)
        try:
            from tools.llm.gemini import plan_humor_localization

            plan = self._plan_fn or plan_humor_localization
            batch = plan(
                script_blocks,
                mode=effective,
                humor_style=job_config.humor_style,
                audience=job_config.audience,
                locale_block=locale_block,
                cultural_summary=cultural_summary,
            )
        except HumorLocalizationError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise HumorLocalizationError(
                f"Humor localization failed: {exc}"
            ) from exc

        if not isinstance(batch, GeminiHumorBatch):
            batch = GeminiHumorBatch.model_validate(batch)

        by_id = {item.clip_id: item for item in batch.items}
        items: list[HumorPlanItem] = []
        for src in script_list:
            gem = by_id.get(src.clip_id)
            if gem is None:
                strategy = "keep" if effective == "original" else "keep"
                items.append(
                    HumorPlanItem(
                        clip_id=src.clip_id,
                        source_humor_present=False,
                        strategy=strategy,
                        rationale="No Gemini item; default to preserve meaning.",
                        suggested_approach="Do not force jokes.",
                    )
                )
                continue
            strategy = (gem.strategy or "keep").strip()
            if strategy not in (
                "keep",
                "adapt",
                "neutralize",
                "drop_joke_keep_meaning",
            ):
                strategy = "keep"
            if effective == "original" and strategy == "adapt":
                strategy = "keep"
            items.append(
                HumorPlanItem(
                    clip_id=src.clip_id,
                    source_humor_present=bool(gem.source_humor_present),
                    strategy=strategy,
                    rationale=(gem.rationale or "").strip(),
                    suggested_approach=(gem.suggested_approach or "").strip(),
                )
            )

        summary = (batch.humor_summary or "").strip()
        if not summary:
            summary = (
                f"Humor mode={effective}; style={job_config.humor_style}. "
                "Never force jokes; preserve meaning when humor does not translate."
            )
        pack.humor_summary = summary
        if summary not in pack.summary_notes:
            pack.summary_notes = list(pack.summary_notes) + [f"Humor: {summary}"]

        report = HumorLocalizationReport(
            project_id=project_id,
            mode=effective,
            humor_style=job_config.humor_style,
            audience=job_config.audience,
            items=items,
            provider="gemini-humor",
            notes=f"Planned humor for {len(items)} clip(s); mode={effective}.",
            humor_summary=summary,
        )
        path = self._write_report(project_id, root, report)
        self._update_locale_context(project_id, root, pack, report)
        messages = [
            f"[{self.name}] Mode: {effective}",
            f"[{self.name}] Items: {len(items)}",
            f"[{self.name}] Wrote analysis/humor_localization.json",
        ]
        logger.info(
            "HumorLocalization ready project_id=%s mode=%s items=%s",
            project_id,
            effective,
            len(items),
        )
        return HumorLocalizationResult(
            humor_localization=report,
            humor_localization_path=str(path),
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

    def _coerce_cultural(
        self,
        cultural: dict[str, Any] | CulturalAdaptationReport | None,
    ) -> CulturalAdaptationReport | None:
        if cultural is None:
            return None
        if isinstance(cultural, CulturalAdaptationReport):
            return cultural
        try:
            return CulturalAdaptationReport.model_validate(cultural)
        except Exception:  # noqa: BLE001
            return None

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
            raise HumorLocalizationError(f"Invalid project metadata: {exc}") from exc

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
            raise HumorLocalizationError(f"Invalid job config: {exc}") from exc

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
            raise HumorLocalizationError(f"Invalid feature flags: {exc}") from exc

    def _write_report(
        self,
        project_id: str,
        root: Path,
        report: HumorLocalizationReport,
    ) -> Path:
        path = root / "analysis" / "humor_localization.json"
        try:
            try:
                canonical = get_humor_localization_path(project_id)
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
                f"Failed to write humor_localization.json: {path}"
            ) from exc
        return path.resolve()

    def _update_locale_context(
        self,
        project_id: str,
        root: Path,
        pack: LocalePack,
        report: HumorLocalizationReport,
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
            existing["humor_localization"] = report.model_dump(mode="json")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        except OSError:
            logger.warning("Could not update locale_context.json for humor agent")
