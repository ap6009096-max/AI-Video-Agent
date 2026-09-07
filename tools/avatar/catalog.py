"""Load and resolve avatar presets from config/avatars.json."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from schemas.avatar import AvatarPack, AvatarPlan, AvatarPreset
from schemas.job import VideoJobConfig
from tools.voice.locale_map import normalize_language

_CATALOG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "avatars.json"


def _norm(value: str) -> str:
    return " ".join(
        (value or "").strip().lower().replace("_", " ").replace("-", " ").split()
    )


@lru_cache(maxsize=1)
def _load_raw() -> list[dict[str, Any]]:
    return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))


def clear_avatar_cache() -> None:
    _load_raw.cache_clear()


def list_avatars() -> list[AvatarPreset]:
    return [AvatarPreset.model_validate(item) for item in _load_raw()]


def resolve_avatar(name_or_id: str) -> AvatarPreset | None:
    key = _norm(name_or_id)
    if not key:
        return None
    for preset in list_avatars():
        if _norm(preset.id) == key or _norm(preset.name) == key:
            return preset
        for alias in preset.aliases:
            if _norm(alias) == key:
                return preset
    return None


def _fallback_none(label: str) -> AvatarPreset:
    return AvatarPreset(
        id="none",
        name=label.strip() or "No Avatar",
        notes="Unknown avatar label — falling back to No Avatar.",
    )


def _voice_fields(voice_pack: dict[str, Any] | None, config: VideoJobConfig) -> tuple[str, str, str]:
    voice = config.voice or ""
    emotion = getattr(config, "voice_emotion", None) or "neutral"
    audio_path = ""
    if isinstance(voice_pack, dict):
        plan = voice_pack.get("plan") or {}
        preset = voice_pack.get("preset") or {}
        if isinstance(preset, dict) and preset.get("name"):
            voice = str(preset.get("name") or voice)
        if isinstance(plan, dict):
            if plan.get("preset_name"):
                voice = str(plan.get("preset_name") or voice)
            if plan.get("emotion"):
                emotion = str(plan.get("emotion") or emotion)
            audio_path = str(
                plan.get("primary_audio_path") or plan.get("audio_path") or ""
            )
    return voice, emotion, audio_path


def _language_fields(
    locale_pack: dict[str, Any] | None,
    config: VideoJobConfig,
    voice_pack: dict[str, Any] | None,
) -> tuple[str, str]:
    language = config.language or "English"
    code = normalize_language(language)
    if isinstance(locale_pack, dict):
        lang_obj = locale_pack.get("language") or {}
        if isinstance(lang_obj, dict):
            if lang_obj.get("name"):
                language = str(lang_obj.get("name") or language)
            if lang_obj.get("code") or lang_obj.get("id"):
                code = normalize_language(
                    str(lang_obj.get("code") or lang_obj.get("id") or code)
                )
    if isinstance(voice_pack, dict):
        plan = voice_pack.get("plan") or {}
        if isinstance(plan, dict):
            if plan.get("language_hint"):
                language = str(plan.get("language_hint") or language)
            if plan.get("language_code"):
                code = normalize_language(str(plan.get("language_code") or code))
    return language, code


def build_avatar_pack(
    avatar_label: str,
    *,
    enabled: bool = True,
    voice_pack: dict[str, Any] | None = None,
    locale_pack: dict[str, Any] | None = None,
    config: VideoJobConfig | None = None,
) -> AvatarPack:
    job = config or VideoJobConfig()
    label = (avatar_label or "").strip() or "No Avatar"
    preset = resolve_avatar(label)
    fallback = False
    if preset is None:
        preset = _fallback_none(label)
        fallback = True

    voice, emotion, audio_path = _voice_fields(voice_pack, job)
    language, lang_code = _language_fields(locale_pack, job, voice_pack)

    expression = (
        (getattr(job, "avatar_expression", None) or "").strip()
        or preset.default_expression
        or "neutral"
    )
    gesture = (
        (getattr(job, "avatar_gesture", None) or "").strip()
        or preset.default_gesture
        or "none"
    )

    is_none = preset.id == "none" or _norm(preset.name) in {"no avatar", "none"}
    skipped = (not enabled) or is_none or fallback

    if skipped:
        plan = AvatarPlan(
            avatar_type=preset.name if is_none else (preset.name or "No Avatar"),
            voice=voice,
            language=language,
            emotion=emotion if enabled else "",
            lip_sync=False,
            gesture="none",
            eye_contact=False,
            expression="neutral",
            speaking_language_code=lang_code if enabled else "",
            audio_path="",
            provider="none",
            provider_ready=False,
            skipped=True,
            gender_hint=preset.gender_hint,
            custom=preset.id == "custom",
            notes=(
                "Avatar feature flag off — skipped."
                if not enabled
                else (
                    "No Avatar mode — skipped."
                    if is_none
                    else "Unknown avatar — skipped."
                )
            ),
        )
    else:
        # Prefer voice emotion when present; else expression as emotion surface
        out_emotion = emotion or expression
        plan = AvatarPlan(
            avatar_type=preset.name,
            voice=voice,
            language=language,
            emotion=out_emotion,
            lip_sync=bool(preset.lip_sync_default),
            gesture=gesture,
            eye_contact=bool(preset.eye_contact_default),
            expression=expression,
            speaking_language_code=lang_code,
            audio_path=audio_path,
            provider="none",
            provider_ready=False,
            skipped=False,
            gender_hint=preset.gender_hint,
            custom=preset.id == "custom",
            notes=(
                f"Avatar planned: {preset.name}. "
                f"lip_sync={preset.lip_sync_default} gesture={gesture} "
                f"eye_contact={preset.eye_contact_default} "
                f"lang={language} ({lang_code}). "
                "Provider not configured — plan only (MVP)."
            ),
        )

    return AvatarPack(
        source_label=label,
        preset=preset,
        plan=plan,
        fallback=fallback,
        notes=plan.notes,
    )
