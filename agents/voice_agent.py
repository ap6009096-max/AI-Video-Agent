"""Voice Agent — multi-language TTS from localized scripts (edge-tts)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agents.base import BaseAgent
from core.errors import StorageError, VoiceAgentError
from core.logging import get_logger
from core.paths import (
    ensure_project_analysis_dir,
    ensure_project_audio_dir,
    ensure_project_dir,
    get_voice_audio_path,
    get_voice_plan_path,
)
from schemas.av_plan import LocalizedVoiceTrack, VoicePack, VoiceResult
from schemas.job import FeatureFlags, VideoJobConfig
from schemas.project import ProjectMetadata
from tools.voice.catalog import build_voice_pack
from tools.voice.locale_map import (
    language_display_name,
    normalize_language,
    resolve_edge_voice,
)
from tools.voice.provider import get_tts_provider

logger = get_logger(__name__)


class VoiceAgent(BaseAgent):
    """Write analysis/voice_plan.json and optional audio/voice_{lang}.mp3."""

    name = "voice"

    def run(
        self,
        project: ProjectMetadata | dict[str, Any],
        *,
        project_dir: str | Path | None = None,
        config: VideoJobConfig | dict[str, Any] | None = None,
        features: FeatureFlags | dict[str, Any] | None = None,
        locale_pack: dict[str, Any] | None = None,
        localizations: dict[str, Any] | None = None,
        scripts: dict[str, Any] | None = None,
        transcript: dict[str, Any] | None = None,
        speech_transcript: dict[str, Any] | None = None,
        **_: Any,
    ) -> VoiceResult:
        meta = self._coerce_project(project)
        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)
        job_config = self._coerce_config(config)
        flags = self._coerce_features(features)

        language, country = self._resolve_locale(job_config, locale_pack)

        try:
            pack = build_voice_pack(
                job_config.voice,
                language=language,
                country=country,
                enabled=bool(flags.voice),
                emotion=getattr(job_config, "voice_emotion", "neutral") or "neutral",
                speed=float(getattr(job_config, "voice_speed", 1.0) or 1.0),
                pitch=float(getattr(job_config, "voice_pitch", 1.0) or 1.0),
            )
        except Exception as exc:  # noqa: BLE001
            raise VoiceAgentError(f"Voice planning failed: {exc}") from exc

        messages = [
            f"[{self.name}] {pack.notes}",
            f"[{self.name}] Preset: {pack.preset.name} "
            f"preserve_original={pack.plan.preserve_original} "
            f"provider={pack.plan.provider}",
        ]

        if not pack.plan.preserve_original and pack.plan.provider_ready:
            pack = self._synthesize_tracks(
                pack,
                project_id=project_id,
                root=root,
                language=language,
                country=country,
                localizations=localizations,
                scripts=scripts,
                transcript=transcript,
                speech_transcript=speech_transcript,
                messages=messages,
            )

        path = self._write_pack(project_id, root, pack)
        messages.append(f"[{self.name}] Wrote analysis/voice_plan.json")
        logger.info(
            "VoiceAgent ready project_id=%s voice=%s preserve=%s tracks=%s",
            project_id,
            pack.preset.name,
            pack.plan.preserve_original,
            len(pack.plan.tracks),
        )
        return VoiceResult(voice_pack=pack, voice_path=str(path), messages=messages)

    def _synthesize_tracks(
        self,
        pack: VoicePack,
        *,
        project_id: str,
        root: Path,
        language: str,
        country: str,
        localizations: dict[str, Any] | None,
        scripts: dict[str, Any] | None,
        transcript: dict[str, Any] | None,
        speech_transcript: dict[str, Any] | None,
        messages: list[str],
    ) -> VoicePack:
        provider = get_tts_provider()
        gender = pack.plan.gender or "neutral"
        targets = self._collect_targets(
            language=language,
            localizations=localizations,
            scripts=scripts,
            transcript=transcript,
            speech_transcript=speech_transcript,
        )
        if not targets:
            pack.plan.preserve_original = True
            pack.plan.notes = (
                (pack.plan.notes or "")
                + " No synthesizable text — preserving original audio."
            ).strip()
            pack.notes = pack.plan.notes
            messages.append(f"[{self.name}] No text for TTS — preserving original.")
            return pack

        try:
            ensure_project_audio_dir(project_id)
        except Exception:  # noqa: BLE001
            (root / "audio").mkdir(parents=True, exist_ok=True)

        tracks: list[LocalizedVoiceTrack] = []
        primary_path = ""
        primary_code = pack.plan.language_code or normalize_language(language)

        for idx, (lang_name, lang_code, text) in enumerate(targets):
            voice_id = resolve_edge_voice(lang_code, gender, country)
            plan_for_syn = pack.plan.model_copy(deep=True)
            plan_for_syn.provider_voice_id = voice_id
            plan_for_syn.language_code = lang_code
            out = get_voice_audio_path(project_id, lang_code)
            # Prefer project root when path helpers point elsewhere
            if root:
                candidate = root / "audio" / f"voice_{lang_code}.mp3"
                candidate.parent.mkdir(parents=True, exist_ok=True)
                out = candidate

            track = LocalizedVoiceTrack(
                language=lang_name or language_display_name(lang_code),
                language_code=lang_code,
                voice_id=voice_id,
                text=text[:2000],
                provider=provider.name,
                accent=country,
                emotion=pack.plan.emotion,
                rate=pack.plan.rate,
                pitch=pack.plan.pitch_ssml,
            )
            try:
                result = provider.synthesize(
                    text, voice_plan=plan_for_syn, out_path=out
                )
            except Exception as exc:  # noqa: BLE001
                track.ok = False
                track.error = str(exc)
                messages.append(
                    f"[{self.name}] TTS soft-failed ({lang_code}): {exc}"
                )
                tracks.append(track)
                continue

            if result is None or not Path(result).is_file():
                track.ok = False
                track.error = "synthesize returned no audio"
                messages.append(
                    f"[{self.name}] TTS soft-failed ({lang_code}): no audio"
                )
                tracks.append(track)
                continue

            track.ok = True
            track.audio_path = str(Path(result).resolve())
            tracks.append(track)
            messages.append(
                f"[{self.name}] Synthesized {lang_code} → {track.audio_path}"
            )
            if idx == 0 or lang_code == primary_code:
                primary_path = track.audio_path
                pack.plan.provider_voice_id = voice_id
                pack.plan.language_code = lang_code

        pack.plan.tracks = tracks
        ok_tracks = [t for t in tracks if t.ok and t.audio_path]
        if ok_tracks:
            if not primary_path:
                primary_path = ok_tracks[0].audio_path
            pack.plan.audio_path = primary_path
            pack.plan.primary_audio_path = primary_path
            pack.plan.preserve_original = False
            pack.plan.notes = (
                (pack.plan.notes or "")
                + f" Generated {len(ok_tracks)} voice track(s)."
            ).strip()
        else:
            pack.plan.preserve_original = True
            pack.plan.notes = (
                (pack.plan.notes or "")
                + " TTS failed for all tracks — preserving original audio."
            ).strip()
            messages.append(f"[{self.name}] All TTS tracks failed — preserving.")
        pack.notes = pack.plan.notes
        return pack

    def _collect_targets(
        self,
        *,
        language: str,
        localizations: dict[str, Any] | None,
        scripts: dict[str, Any] | None,
        transcript: dict[str, Any] | None,
        speech_transcript: dict[str, Any] | None,
    ) -> list[tuple[str, str, str]]:
        """Return list of (language_name, code, text) — primary first."""
        primary_code = normalize_language(language)
        primary_name = language
        seen: set[str] = set()
        out: list[tuple[str, str, str]] = []

        versions = []
        if isinstance(localizations, dict):
            versions = localizations.get("versions") or []
            if not isinstance(versions, list):
                versions = []

        # Prefer matching localization version for primary language
        primary_text = ""
        for ver in versions:
            if not isinstance(ver, dict):
                continue
            name, code = self._version_language(ver)
            text = self._join_scripts(ver.get("scripts"))
            if not text:
                continue
            if normalize_language(code or name) == primary_code and not primary_text:
                primary_text = text
                primary_name = name or primary_name

        if not primary_text:
            primary_text = self._join_scripts(
                (scripts or {}).get("scripts") if isinstance(scripts, dict) else None
            )
        if not primary_text:
            primary_text = self._transcript_text(transcript, speech_transcript)

        if primary_text:
            out.append((primary_name, primary_code, primary_text))
            seen.add(primary_code)

        for ver in versions:
            if not isinstance(ver, dict):
                continue
            name, code = self._version_language(ver)
            lang_code = normalize_language(code or name)
            if lang_code in seen:
                continue
            text = self._join_scripts(ver.get("scripts"))
            if not text:
                continue
            out.append((name or language_display_name(lang_code), lang_code, text))
            seen.add(lang_code)

        return out

    @staticmethod
    def _version_language(ver: dict[str, Any]) -> tuple[str, str]:
        target = ver.get("target") or {}
        locale = ver.get("locale_pack") or {}
        lang_obj = {}
        if isinstance(locale, dict):
            lang_obj = locale.get("language") or {}
        name = ""
        code = ""
        if isinstance(target, dict):
            name = str(target.get("language") or "")
        if isinstance(lang_obj, dict):
            name = name or str(lang_obj.get("name") or "")
            code = str(lang_obj.get("code") or lang_obj.get("id") or "")
        return name, code

    @staticmethod
    def _join_scripts(scripts: Any) -> str:
        if not isinstance(scripts, list):
            return ""
        parts: list[str] = []
        for item in scripts:
            if not isinstance(item, dict):
                continue
            for key in ("short_script", "caption", "hook", "title"):
                val = str(item.get(key) or "").strip()
                if val:
                    parts.append(val)
                    break
        return "\n\n".join(parts).strip()

    @staticmethod
    def _transcript_text(
        transcript: dict[str, Any] | None,
        speech_transcript: dict[str, Any] | None,
    ) -> str:
        for blob in (transcript, speech_transcript):
            if not isinstance(blob, dict):
                continue
            for key in ("text", "full_text", "cleaned_text"):
                val = str(blob.get(key) or "").strip()
                if val:
                    return val[:4000]
            structured = blob.get("structured") or blob.get("transcript")
            if isinstance(structured, dict):
                val = str(structured.get("text") or "").strip()
                if val:
                    return val[:4000]
        return ""

    @staticmethod
    def _resolve_locale(
        job_config: VideoJobConfig,
        locale_pack: dict[str, Any] | None,
    ) -> tuple[str, str]:
        language = job_config.language or "English"
        country = job_config.country or ""
        if isinstance(locale_pack, dict):
            lang_obj = locale_pack.get("language") or {}
            if isinstance(lang_obj, dict) and lang_obj.get("name"):
                language = str(lang_obj.get("name") or language)
            country_obj = locale_pack.get("country") or {}
            if isinstance(country_obj, dict):
                country = str(
                    country_obj.get("name") or country_obj.get("id") or country
                )
        return language, country

    def _coerce_project(
        self, project: ProjectMetadata | dict[str, Any]
    ) -> ProjectMetadata:
        if isinstance(project, ProjectMetadata):
            return project
        try:
            return ProjectMetadata.model_validate(project)
        except Exception as exc:  # noqa: BLE001
            raise VoiceAgentError(f"Invalid project metadata: {exc}") from exc

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
            raise VoiceAgentError(f"Invalid job config: {exc}") from exc

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
            raise VoiceAgentError(f"Invalid feature flags: {exc}") from exc

    def _write_pack(
        self,
        project_id: str,
        root: Path,
        pack: VoicePack,
    ) -> Path:
        path = root / "analysis" / "voice_plan.json"
        try:
            try:
                canonical = get_voice_plan_path(project_id)
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
            raise StorageError(f"Failed to write voice_plan.json: {path}") from exc
        return path.resolve()
