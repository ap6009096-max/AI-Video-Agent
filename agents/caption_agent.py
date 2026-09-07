"""Caption Agent — timed cues from transcripts, subtitle export, optional burn-in."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agents.base import BaseAgent
from core.errors import CaptionAgentError, StorageError
from core.logging import get_logger
from core.paths import (
    ensure_project_analysis_dir,
    ensure_project_captions_dir,
    ensure_project_dir,
    get_captions_plan_path,
)
from schemas.captions import CaptionPack, CaptionPlan, CaptionResult
from schemas.job import FeatureFlags, VideoJobConfig
from schemas.project import ProjectMetadata
from tools.captions.burnin import burn_captions
from tools.captions.catalog import (
    default_caption_style,
    default_safe_area,
    resolve_caption_style,
    resolve_safe_area,
)
from tools.captions.cues import (
    build_localized_track,
    build_primary_track,
    build_sentence_cues,
    build_word_cues,
    enrich_cues_with_words,
)
from tools.captions.export import (
    ass_is_useful,
    style_effects,
    write_ass,
    write_srt,
    write_vtt,
)

logger = get_logger(__name__)


class CaptionAgent(BaseAgent):
    """Write captions_plan.json + SRT/VTT/ASS; burn-in when media + FFmpeg exist."""

    name = "captions"

    def run(
        self,
        project: ProjectMetadata | dict[str, Any],
        *,
        project_dir: str | Path | None = None,
        config: VideoJobConfig | dict[str, Any] | None = None,
        features: FeatureFlags | dict[str, Any] | None = None,
        speech_transcript: dict[str, Any] | None = None,
        transcript: dict[str, Any] | None = None,
        localizations: dict[str, Any] | None = None,
        locale_pack: dict[str, Any] | None = None,
        source_metadata: dict[str, Any] | None = None,
        **_: Any,
    ) -> CaptionResult:
        meta = self._coerce_project(project)
        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)
        job_config = self._coerce_config(config)
        flags = self._coerce_features(features)

        style = (
            resolve_caption_style(job_config.caption_style) or default_caption_style()
        )
        safe = resolve_safe_area(job_config.platform) or default_safe_area()
        emoji_enabled = bool(job_config.caption_emoji) and bool(style.emoji_allowed)
        burn_requested = bool(job_config.caption_burn_in)

        language = job_config.language or ""
        direction = self._script_direction(locale_pack, localizations)

        notes_parts: list[str] = []

        if not flags.captions:
            pack = CaptionPack(
                plan=CaptionPlan(
                    project_id=project_id,
                    timed=False,
                    skipped=True,
                    style_name=style.name,
                    platform=job_config.platform,
                    emoji_enabled=False,
                    burn_in_requested=burn_requested,
                    burn_in_applied=False,
                    notes="Captions feature flag off — skipped.",
                ),
                style=style,
                safe_area=safe,
                notes="Captions feature flag off — skipped.",
            )
            path = self._write_pack(project_id, root, pack)
            return CaptionResult(
                captions_pack=pack,
                captions_path=str(path),
                messages=[
                    f"[{self.name}] Captions skipped (feature flag off).",
                    f"[{self.name}] Wrote analysis/captions_plan.json",
                ],
            )

        try:
            word_cues = build_word_cues(
                speech_transcript, emoji_enabled=emoji_enabled
            )
            sentence_cues = build_sentence_cues(
                speech_transcript,
                transcript,
                emoji_enabled=emoji_enabled,
            )
        except Exception as exc:  # noqa: BLE001
            raise CaptionAgentError(f"Caption cue building failed: {exc}") from exc

        timed = bool(sentence_cues or word_cues)
        if not timed:
            notes_parts.append(
                "No usable transcript timestamps — exports and burn-in skipped "
                "(never invent timing)."
            )
            pack = CaptionPack(
                plan=CaptionPlan(
                    project_id=project_id,
                    timed=False,
                    skipped=False,
                    style_name=style.name,
                    platform=job_config.platform,
                    emoji_enabled=emoji_enabled,
                    burn_in_requested=burn_requested,
                    burn_in_applied=False,
                    notes=" ".join(notes_parts),
                ),
                style=style,
                safe_area=safe,
                notes=" ".join(notes_parts),
            )
            path = self._write_pack(project_id, root, pack)
            return CaptionResult(
                captions_pack=pack,
                captions_path=str(path),
                messages=[
                    f"[{self.name}] {pack.notes}",
                    f"[{self.name}] Wrote analysis/captions_plan.json",
                ],
            )

        primary = build_primary_track(
            language=language
            or (
                str((speech_transcript or {}).get("language") or "")
                if isinstance(speech_transcript, dict)
                else ""
            ),
            direction=direction,
            sentence_cues=sentence_cues,
        )
        localized, loc_note = build_localized_track(
            sentence_cues,
            localizations,
            language=language,
            direction=direction,
            emoji_enabled=emoji_enabled,
        )
        if loc_note:
            notes_parts.append(loc_note)

        # Karaoke/word_highlight styles need word timings on sentence cues
        effects = style_effects(style)
        if effects & {"word_highlight", "karaoke"}:
            sentence_cues = enrich_cues_with_words(sentence_cues, word_cues)
            primary = build_primary_track(
                language=primary.language,
                direction=str(primary.direction),
                sentence_cues=sentence_cues,
            )

        export_cues = sentence_cues or word_cues
        captions_dir = root / "captions"
        captions_dir.mkdir(parents=True, exist_ok=True)
        try:
            ensure_project_captions_dir(project_id)
        except Exception:  # noqa: BLE001
            pass

        srt_path = ""
        vtt_path = ""
        ass_path = ""
        burned_path = ""
        burn_applied = False

        try:
            srt_file = write_srt(captions_dir / "captions.srt", export_cues)
            srt_path = str(srt_file)
            vtt_file = write_vtt(captions_dir / "captions.vtt", export_cues)
            vtt_path = str(vtt_file)
            notes_parts.append(f"Exported SRT/VTT ({len(export_cues)} cues).")

            if ass_is_useful(style, burn_in=burn_requested):
                ass_file = write_ass(
                    captions_dir / "captions.ass",
                    primary if primary.cues else build_primary_track(
                        language=language,
                        direction=direction,
                        sentence_cues=export_cues,
                    ),
                    style,
                    safe,
                )
                ass_path = str(ass_file)
                eff = sorted(style_effects(style))
                notes_parts.append(
                    f"Exported ASS (style={style.name}, "
                    f"animation={style.animation}, effects={eff})."
                )
                if style.name in {"TikTok", "Shorts", "Reels", "Gaming"} and not burn_requested:
                    notes_parts.append(
                        "Burn-in off — enable caption burn-in to see karaoke/motion in video."
                    )

            if burn_requested:
                media = self._resolve_media_path(meta, source_metadata, speech_transcript)
                sub_for_burn = ass_path or srt_path
                if media and sub_for_burn:
                    out = burn_captions(
                        media,
                        sub_for_burn,
                        captions_dir / "burned_in.mp4",
                    )
                    if out is not None and out.is_file():
                        burned_path = str(out)
                        burn_applied = True
                        notes_parts.append("Burned-in captions written.")
                    else:
                        notes_parts.append(
                            "Burn-in soft-skipped (FFmpeg/media unavailable or failed)."
                        )
                else:
                    notes_parts.append(
                        "Burn-in soft-skipped (no media path or subtitle file)."
                    )
        except OSError as exc:
            raise StorageError(f"Failed to write caption exports: {exc}") from exc

        pack = CaptionPack(
            plan=CaptionPlan(
                project_id=project_id,
                timed=True,
                skipped=False,
                style_name=style.name,
                platform=job_config.platform,
                emoji_enabled=emoji_enabled,
                burn_in_requested=burn_requested,
                burn_in_applied=burn_applied,
                notes=" ".join(notes_parts),
            ),
            style=style,
            safe_area=safe,
            primary_track=primary,
            localized_track=localized,
            word_cues=word_cues,
            sentence_cues=sentence_cues,
            srt_path=srt_path,
            vtt_path=vtt_path,
            ass_path=ass_path,
            burned_in_path=burned_path,
            notes=" ".join(notes_parts),
        )
        # Honesty: never claim burn-in without a real file
        if pack.plan.burn_in_applied and not (pack.burned_in_path or "").strip():
            pack.plan.burn_in_applied = False

        path = self._write_pack(project_id, root, pack)
        messages = [
            f"[{self.name}] {pack.notes}",
            f"[{self.name}] Style={style.name} platform={safe.name} "
            f"words={len(word_cues)} sentences={len(sentence_cues)}",
            f"[{self.name}] Wrote analysis/captions_plan.json",
        ]
        logger.info(
            "CaptionAgent ready project_id=%s timed=%s cues=%s burn=%s",
            project_id,
            timed,
            len(export_cues),
            burn_applied,
        )
        return CaptionResult(
            captions_pack=pack, captions_path=str(path), messages=messages
        )

    def _coerce_project(
        self, project: ProjectMetadata | dict[str, Any]
    ) -> ProjectMetadata:
        if isinstance(project, ProjectMetadata):
            return project
        try:
            return ProjectMetadata.model_validate(project)
        except Exception as exc:  # noqa: BLE001
            raise CaptionAgentError(f"Invalid project metadata: {exc}") from exc

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
            raise CaptionAgentError(f"Invalid job config: {exc}") from exc

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
            raise CaptionAgentError(f"Invalid feature flags: {exc}") from exc

    def _script_direction(
        self,
        locale_pack: dict[str, Any] | None,
        localizations: dict[str, Any] | None,
    ) -> str:
        for blob in (locale_pack, localizations):
            if not isinstance(blob, dict):
                continue
            lang = blob.get("language") or {}
            if isinstance(lang, dict):
                direction = str(lang.get("script_direction") or "").strip().lower()
                if direction in ("ltr", "rtl"):
                    return direction
            versions = blob.get("versions") or []
            if isinstance(versions, list) and versions:
                v0 = versions[0]
                if isinstance(v0, dict):
                    tlang = v0.get("language") or {}
                    if isinstance(tlang, dict):
                        direction = str(
                            tlang.get("script_direction") or ""
                        ).strip().lower()
                        if direction in ("ltr", "rtl"):
                            return direction
        return "ltr"

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
        if getattr(meta, "source_path", None):
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
        pack: CaptionPack,
    ) -> Path:
        path = root / "analysis" / "captions_plan.json"
        try:
            try:
                canonical = get_captions_plan_path(project_id)
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
            raise StorageError(f"Failed to write captions_plan.json: {path}") from exc
        return path.resolve()
