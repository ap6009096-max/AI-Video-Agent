"""Character catalog — cast bible builder for cross-scene consistency."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

from config.settings import get_settings
from schemas.character import (
    CharacterPack,
    CharacterPlan,
    CharacterProfile,
    CharacterRoleType,
    GeminiCharacterBatch,
)
from schemas.job import VideoJobConfig

_CATALOG_PATH = (
    Path(__file__).resolve().parent.parent.parent / "config" / "characters.json"
)

_VALID_ROLES: set[str] = {
    "human",
    "narrator",
    "ai_avatar",
    "mascot",
    "animated",
}

AnalyzeFn = Callable[..., GeminiCharacterBatch]


@lru_cache(maxsize=1)
def _load_raw() -> dict[str, Any]:
    return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))


def clear_character_cache() -> None:
    _load_raw.cache_clear()


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _norm_role(value: str) -> CharacterRoleType:
    key = _safe_str(value).lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "aiavatar": "ai_avatar",
        "avatar": "ai_avatar",
        "ai_avatar": "ai_avatar",
        "voiceover": "narrator",
        "vo": "narrator",
        "animation": "animated",
        "cartoon": "animated",
    }
    key = aliases.get(key, key)
    if key in _VALID_ROLES:
        return key  # type: ignore[return-value]
    return "human"


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text or "")
    return [p.strip() for p in parts if p and p.strip()]


def _gather_signals(
    script_pack: dict[str, Any] | None,
    storyboard_pack: dict[str, Any] | None,
    stories: dict[str, Any] | None,
    visual_style_pack: dict[str, Any] | None,
    environment_pack: dict[str, Any] | None,
    config: VideoJobConfig,
) -> dict[str, Any]:
    title = ""
    hook = ""
    script_bits: list[str] = []
    story_bits: list[str] = []
    storyboard_rows: list[dict[str, Any]] = []

    style = _safe_str(config.visual_style) or "Cinematic"
    environment = _safe_str(config.environment) or "Wildlife/Nature Forest"
    voice_hint = _safe_str(getattr(config, "voice", "") or "")
    avatar_hint = _safe_str(getattr(config, "avatar", "") or "")

    if isinstance(visual_style_pack, dict):
        plan = visual_style_pack.get("plan") or visual_style_pack
        if isinstance(plan, dict):
            style = _safe_str(plan.get("name") or plan.get("style") or style)
        style = _safe_str(visual_style_pack.get("name") or style)

    if isinstance(environment_pack, dict):
        plan = environment_pack.get("plan") or environment_pack
        if isinstance(plan, dict):
            environment = _safe_str(
                plan.get("name") or plan.get("environment") or environment
            )
        environment = _safe_str(environment_pack.get("name") or environment)

    if isinstance(script_pack, dict):
        primary = script_pack.get("primary") or script_pack.get("script")
        if isinstance(primary, dict):
            title = _safe_str(primary.get("title") or title)
            hook = _safe_str(primary.get("hook") or hook)
            body = _safe_str(
                primary.get("script")
                or primary.get("short_script")
                or primary.get("caption")
            )
            if body:
                script_bits.append(body)
        scripts = script_pack.get("scripts") or script_pack.get("items")
        if isinstance(scripts, list):
            for s in scripts[:4]:
                if not isinstance(s, dict):
                    continue
                title = title or _safe_str(s.get("title"))
                hook = hook or _safe_str(s.get("hook"))
                body = _safe_str(
                    s.get("script") or s.get("short_script") or s.get("caption")
                )
                if body:
                    script_bits.append(body)

    if isinstance(stories, dict):
        items = stories.get("stories") or stories.get("items") or stories.get("beats")
        if isinstance(items, list):
            for item in items[:8]:
                if isinstance(item, dict):
                    beat = _safe_str(
                        item.get("summary")
                        or item.get("beat")
                        or item.get("title")
                        or item.get("text")
                    )
                    if beat:
                        story_bits.append(beat)
                elif item:
                    story_bits.append(_safe_str(item))

    if isinstance(storyboard_pack, dict):
        plan = storyboard_pack.get("plan") or {}
        shots = plan.get("shots") if isinstance(plan, dict) else None
        if isinstance(shots, list) and not plan.get("skipped"):
            for s in shots:
                if isinstance(s, dict):
                    storyboard_rows.append(s)

    return {
        "title": title,
        "hook": hook,
        "style": style,
        "environment": environment,
        "voice_hint": voice_hint,
        "avatar_hint": avatar_hint,
        "script_block": "\n".join(script_bits)[:1600],
        "story_block": "\n".join(story_bits)[:1200],
        "storyboard_rows": storyboard_rows,
        "storyboard_block": "\n".join(
            f"scene {r.get('scene')}: cam={r.get('camera')}; "
            f"visual={r.get('visual')}; vo={r.get('voiceover')}; "
            f"trans={r.get('transition')}"
            for r in storyboard_rows[:12]
        )[:1600],
        "scene_ids": [
            int(r.get("scene") or i)
            for i, r in enumerate(storyboard_rows[:12], start=1)
            if True
        ],
    }


def _defaults_for(role: CharacterRoleType, catalog: dict[str, Any]) -> dict[str, Any]:
    roles = catalog.get("role_types") or {}
    return dict(roles.get(role) or roles.get("human") or {})


def _heuristic_batch(
    catalog: dict[str, Any],
    signals: dict[str, Any],
) -> GeminiCharacterBatch:
    max_chars = int(catalog.get("max_characters") or 6)
    templates = list(catalog.get("consistency_templates") or [])
    scene_ids = list(signals.get("scene_ids") or [1])
    style = signals["style"]
    environment = signals["environment"]
    avatar_hint = (signals.get("avatar_hint") or "").lower()
    video_hint = style.lower()

    characters: list[CharacterProfile] = []

    # Narrator when VO-heavy storyboard or voice config
    has_vo = any(_safe_str(r.get("voiceover")) for r in signals.get("storyboard_rows") or [])
    if has_vo or signals.get("script_block"):
        d = _defaults_for("narrator", catalog)
        characters.append(
            CharacterProfile(
                name="Narrator",
                role_type="narrator",
                appearance=_safe_str(d.get("appearance")),
                clothing=_safe_str(d.get("clothing")),
                voice=_safe_str(signals.get("voice_hint"))
                or _safe_str(d.get("voice")),
                personality=_safe_str(d.get("personality")),
                expressions=list(d.get("expressions") or []),
                scene_ids=list(scene_ids),
            )
        )

    # On-screen lead
    if "animation" in video_hint or "animated" in video_hint:
        role: CharacterRoleType = "animated"
        name = "Lead Character"
    elif "mascot" in video_hint:
        role = "mascot"
        name = "Mascot"
    elif avatar_hint and "no avatar" not in avatar_hint and avatar_hint not in {
        "none",
        "off",
        "disabled",
        "",
    }:
        role = "ai_avatar"
        name = "AI Presenter"
    else:
        role = "human"
        name = "Host"

    d = _defaults_for(role, catalog)
    characters.append(
        CharacterProfile(
            name=name,
            role_type=role,
            appearance=(
                f"{_safe_str(d.get('appearance'))}; style={style}; env={environment}"
            ),
            clothing=_safe_str(d.get("clothing")),
            voice=_safe_str(d.get("voice")),
            personality=_safe_str(d.get("personality")),
            expressions=list(d.get("expressions") or []),
            scene_ids=list(scene_ids),
        )
    )

    characters = characters[:max_chars]
    consistency_notes: list[str] = []
    scenes_label = ", ".join(str(s) for s in scene_ids) or "all"
    for c in characters:
        for tmpl in templates:
            try:
                consistency_notes.append(
                    tmpl.format(
                        name=c.name,
                        scenes=scenes_label,
                        clothing=c.clothing or "same outfit",
                        voice=c.voice or "same voice",
                        personality=c.personality or "same personality",
                        expressions=", ".join(c.expressions) or "approved set",
                    )
                )
            except (KeyError, ValueError):
                consistency_notes.append(
                    f"Keep {c.name} appearance/clothing/voice consistent across scenes {scenes_label}."
                )

    return GeminiCharacterBatch(
        characters=characters,
        consistency_notes=consistency_notes[: max_chars * 4],
        notes="Heuristic character bible from script/storyboard.",
    )


def _normalize_characters(
    raw: list[CharacterProfile],
    catalog: dict[str, Any],
    signals: dict[str, Any],
) -> list[CharacterProfile]:
    max_chars = int(catalog.get("max_characters") or 6)
    out: list[CharacterProfile] = []
    seen: set[str] = set()
    for c in list(raw)[:max_chars]:
        name = _safe_str(c.name) or f"Character {len(out) + 1}"
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        role = _norm_role(str(c.role_type))
        d = _defaults_for(role, catalog)
        exprs = [ _safe_str(e) for e in (c.expressions or []) if _safe_str(e) ]
        if not exprs:
            exprs = [str(e) for e in (d.get("expressions") or [])]
        scene_ids = [int(s) for s in (c.scene_ids or signals.get("scene_ids") or []) if True]
        try:
            scene_ids = [int(s) for s in scene_ids if int(s) >= 1]
        except (TypeError, ValueError):
            scene_ids = list(signals.get("scene_ids") or [])
        out.append(
            CharacterProfile(
                name=name,
                role_type=role,
                appearance=_safe_str(c.appearance) or _safe_str(d.get("appearance")),
                clothing=_safe_str(c.clothing) or _safe_str(d.get("clothing")),
                voice=_safe_str(c.voice) or _safe_str(d.get("voice")),
                personality=_safe_str(c.personality) or _safe_str(d.get("personality")),
                expressions=exprs,
                scene_ids=scene_ids,
            )
        )
    return out


def build_character_pack(
    *,
    enabled: bool = True,
    config: VideoJobConfig | None = None,
    script_pack: dict[str, Any] | None = None,
    storyboard_pack: dict[str, Any] | None = None,
    stories: dict[str, Any] | None = None,
    visual_style_pack: dict[str, Any] | None = None,
    environment_pack: dict[str, Any] | None = None,
    analyze_fn: AnalyzeFn | None = None,
) -> CharacterPack:
    job = config or VideoJobConfig()
    catalog = _load_raw()
    signals = _gather_signals(
        script_pack,
        storyboard_pack,
        stories,
        visual_style_pack,
        environment_pack,
        job,
    )
    label = signals["style"] or "Characters"

    if not enabled:
        plan = CharacterPlan(
            provider="none",
            skipped=True,
            notes="Character feature flag off — skipped.",
        )
        return CharacterPack(source_label=label, plan=plan, notes=plan.notes)

    batch: GeminiCharacterBatch | None = None
    provider = "heuristic"
    notes_extra = ""
    fallback = False

    settings = get_settings()
    use_gemini = bool(analyze_fn is not None or settings.has_gemini_api_key)
    if use_gemini:
        try:
            from tools.llm.gemini import analyze_characters

            fn = analyze_fn or analyze_characters
            roles = catalog.get("role_types") or {}
            role_defaults = "\n".join(
                f"{k}: appearance={v.get('appearance')}; clothing={v.get('clothing')}"
                for k, v in roles.items()
                if isinstance(v, dict)
            )
            batch = fn(
                style=signals["style"],
                environment=signals["environment"],
                audience=job.audience or "General",
                title=signals["title"],
                hook=signals["hook"],
                script_block=signals["script_block"],
                storyboard_block=signals["storyboard_block"],
                story_block=signals["story_block"],
                voice_hint=signals["voice_hint"],
                avatar_hint=signals["avatar_hint"],
                role_defaults=role_defaults,
            )
            provider = "gemini"
        except Exception as exc:  # noqa: BLE001
            notes_extra = f" Gemini failed ({exc}); heuristic fallback."
            batch = None
            provider = "heuristic"
            fallback = True

    if batch is None:
        batch = _heuristic_batch(catalog, signals)
        provider = "heuristic"
        fallback = True

    characters = _normalize_characters(
        list(batch.characters or []), catalog, signals
    )
    consistency_notes = [
        _safe_str(n) for n in (batch.consistency_notes or []) if _safe_str(n)
    ]
    if not consistency_notes and characters:
        consistency_notes = [
            f"Keep {c.name} appearance, clothing, and voice identical across scenes."
            for c in characters
        ]

    plan = CharacterPlan(
        characters=characters,
        consistency_notes=consistency_notes,
        provider=provider,
        skipped=False,
        notes=(
            f"Character bible via {provider} "
            f"({len(characters)} cast).{notes_extra} Plan only."
        ),
    )
    return CharacterPack(
        source_label=label,
        plan=plan,
        fallback=fallback,
        notes=plan.notes,
    )
