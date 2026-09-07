"""Language Agent — natural localization of scripts into one or more locales."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from agents.base import BaseAgent
from core.errors import LanguageAgentError, StorageError
from core.logging import get_logger
from core.paths import (
    ensure_project_analysis_dir,
    ensure_project_dir,
    get_localizations_path,
)
from schemas.job import FeatureFlags, VideoJobConfig
from schemas.localization import (
    GeminiLocalizedBatch,
    GeminiLocalizedClip,
    LocalePack,
    LocalizationReport,
    LocalizationResult,
    LocalizationTarget,
    LocalizedClipScript,
    LocalizedVersion,
)
from schemas.project import ProjectMetadata
from schemas.story import ClipScript, ScriptsReport
from tools.localization.catalog import (
    build_locale_pack,
    expand_targets,
    locale_pack_prompt_block,
)

logger = get_logger(__name__)

LocalizeFn = Callable[..., GeminiLocalizedBatch]


class LanguageAgent(BaseAgent):
    """Write analysis/localizations.json from scripts + locale packs via Gemini."""

    name = "language"

    def __init__(self, localize_fn: LocalizeFn | None = None) -> None:
        self._localize_fn = localize_fn

    def run(
        self,
        project: ProjectMetadata | dict[str, Any],
        *,
        project_dir: str | Path | None = None,
        config: VideoJobConfig | dict[str, Any] | None = None,
        features: FeatureFlags | dict[str, Any] | None = None,
        scripts: dict[str, Any] | ScriptsReport | None = None,
        country_profile: dict[str, Any] | None = None,
        region_profile: dict[str, Any] | None = None,
        locale_pack: dict[str, Any] | LocalePack | None = None,
        **_: Any,
    ) -> LocalizationResult:
        meta = self._coerce_project(project)
        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)
        job_config = self._coerce_config(config)
        flags = self._coerce_features(features)
        script_list = self._parse_scripts(scripts)

        targets = expand_targets(
            country=job_config.country,
            region=job_config.region,
            language=job_config.language,
            localization_targets=job_config.localization_targets,
            cultural_adaptation=bool(flags.cultural_adaptation),
        )

        if not script_list:
            notes = "No scripts available — localization skipped."
            report = LocalizationReport(
                project_id=project_id,
                versions=[],
                provider="skipped",
                notes=notes,
            )
            path = self._write_report(project_id, root, report)
            return LocalizationResult(
                localizations=report,
                localizations_path=str(path),
                messages=[f"[{self.name}] {notes}"],
            )

        from tools.llm.gemini import localize_clip_scripts

        localize = self._localize_fn or localize_clip_scripts
        versions: list[LocalizedVersion] = []

        for target in targets:
            pack = build_locale_pack(
                target,
                include_regional_humor=bool(flags.regional_humor),
                voice=job_config.voice,
            )
            pack.audience = job_config.audience
            pack.humor_adaptation = job_config.humor_adaptation
            pack.humor_style = job_config.humor_style

            # Prefer upstream enriched pack (cultural/humor summaries) when matching
            upstream: LocalePack | None = None
            if isinstance(locale_pack, LocalePack):
                upstream = locale_pack
            elif isinstance(locale_pack, dict) and locale_pack:
                try:
                    upstream = LocalePack.model_validate(locale_pack)
                except Exception:  # noqa: BLE001
                    upstream = None
            if upstream is not None:
                if (
                    upstream.target.language == pack.target.language
                    and upstream.target.country == pack.target.country
                ):
                    pack = upstream.model_copy(deep=True)
                else:
                    # Carry cultural/humor guidance into other locale variants
                    pack.cultural_summary = upstream.cultural_summary or pack.cultural_summary
                    pack.humor_summary = upstream.humor_summary or pack.humor_summary
                    pack.humor_adaptation = (
                        upstream.humor_adaptation or pack.humor_adaptation
                    )
                    pack.humor_style = upstream.humor_style or pack.humor_style
                    pack.audience = upstream.audience or pack.audience
                    pack.include_regional_humor = (
                        upstream.include_regional_humor or pack.include_regional_humor
                    )

            script_blocks = [self._format_script_block(s) for s in script_list]
            locale_block = locale_pack_prompt_block(pack)
            try:
                batch = localize(script_blocks, locale_block=locale_block)
            except LanguageAgentError:
                raise
            except Exception as exc:  # noqa: BLE001
                raise LanguageAgentError(
                    f"Localization failed for {target.language}: {exc}"
                ) from exc

            if not isinstance(batch, GeminiLocalizedBatch):
                batch = GeminiLocalizedBatch.model_validate(batch)

            by_id = {item.clip_id: item for item in batch.scripts}
            localized: list[LocalizedClipScript] = []
            for src in script_list:
                gem = by_id.get(src.clip_id)
                localized.append(self._merge_localized(gem, src, pack.target, pack))
            versions.append(
                LocalizedVersion(target=pack.target, locale_pack=pack, scripts=localized)
            )

        report = LocalizationReport(
            project_id=project_id,
            versions=versions,
            provider="gemini-localization",
            notes=(
                f"Produced {len(versions)} localized version(s); "
                "natural adaptation, meaning preserved."
            ),
        )
        path = self._write_report(project_id, root, report)
        messages = [
            f"[{self.name}] Localized versions: {len(versions)}",
            f"[{self.name}] Targets: "
            + ", ".join(
                f"{v.target.country}/{v.target.region or '-'}/{v.target.language}"
                for v in versions
            ),
            f"[{self.name}] Wrote analysis/localizations.json",
        ]
        logger.info(
            "LanguageAgent ready project_id=%s versions=%s",
            project_id,
            len(versions),
        )
        return LocalizationResult(
            localizations=report,
            localizations_path=str(path),
            messages=messages,
        )

    def _format_script_block(self, script: ClipScript) -> str:
        return (
            f"### clip_id={script.clip_id}\n"
            f"title: {script.title}\n"
            f"hook: {script.hook}\n"
            f"short_script: {script.short_script}\n"
            f"caption: {script.caption}\n"
            f"cta: {script.cta}\n"
            f"thumbnail_text: {script.thumbnail_text}\n"
            f"keywords: {', '.join(script.keywords)}"
        )

    def _merge_localized(
        self,
        gem: GeminiLocalizedClip | None,
        src: ClipScript,
        target: LocalizationTarget,
        pack: LocalePack,
    ) -> LocalizedClipScript:
        voice_fallback = pack.language.voice_notes if pack.language else ""
        if pack.country and pack.country.voice_hints:
            voice_fallback = (
                f"{voice_fallback}; {pack.country.voice_hints}".strip("; ")
                if voice_fallback
                else pack.country.voice_hints
            )
        voice_fallback = f"{job_voice(pack)} {voice_fallback}".strip()

        if gem is None:
            return LocalizedClipScript(
                clip_id=src.clip_id,
                title=src.title,
                hook=src.hook,
                short_script=src.short_script,
                caption=src.caption,
                cta=src.cta,
                thumbnail_text=src.thumbnail_text,
                keywords=list(src.keywords),
                voice_direction=voice_fallback,
                locale=target,
            )

        return LocalizedClipScript(
            clip_id=src.clip_id,
            title=(gem.title or "").strip() or src.title,
            hook=(gem.hook or "").strip() or src.hook,
            short_script=(gem.short_script or "").strip() or src.short_script,
            caption=(gem.caption or "").strip() or src.caption,
            cta=(gem.cta or "").strip() or src.cta,
            thumbnail_text=(gem.thumbnail_text or "").strip() or src.thumbnail_text,
            keywords=[k.strip() for k in (gem.keywords or []) if str(k).strip()]
            or list(src.keywords),
            voice_direction=(gem.voice_direction or "").strip() or voice_fallback,
            locale=target,
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

    def _coerce_project(self, project: ProjectMetadata | dict[str, Any]) -> ProjectMetadata:
        if isinstance(project, ProjectMetadata):
            return project
        try:
            return ProjectMetadata.model_validate(project)
        except Exception as exc:  # noqa: BLE001
            raise LanguageAgentError(f"Invalid project metadata: {exc}") from exc

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
            raise LanguageAgentError(f"Invalid job config: {exc}") from exc

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
            raise LanguageAgentError(f"Invalid feature flags: {exc}") from exc

    def _write_report(
        self,
        project_id: str,
        root: Path,
        report: LocalizationReport,
    ) -> Path:
        path = root / "analysis" / "localizations.json"
        try:
            try:
                canonical = get_localizations_path(project_id)
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
            raise StorageError(f"Failed to write localizations.json: {path}") from exc
        return path.resolve()


def job_voice(pack: LocalePack) -> str:
    return (pack.voice or "").strip()
