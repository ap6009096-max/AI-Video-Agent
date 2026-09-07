"""Build platform optimization packs from scripts + catalog (no publish)."""

from __future__ import annotations

import re
from typing import Any

from schemas.platform import (
    PlatformExportHints,
    PlatformMetadata,
    PlatformPack,
    PlatformPlan,
    PlatformPreset,
    SafeTextArea,
)
from tools.platforms.catalog import resolve_or_fallback

_HASH_RE = re.compile(r"[^a-zA-Z0-9_]+")


def _first_script(scripts: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(scripts, dict):
        return {}
    items = scripts.get("scripts") or []
    if isinstance(items, list) and items and isinstance(items[0], dict):
        return items[0]
    return {}


def _localized_script(localizations: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(localizations, dict):
        return {}
    versions = localizations.get("versions") or []
    if not isinstance(versions, list) or not versions:
        return {}
    v0 = versions[0]
    if not isinstance(v0, dict):
        return {}
    scripts = v0.get("scripts") or []
    if isinstance(scripts, list) and scripts and isinstance(scripts[0], dict):
        return scripts[0]
    return {}


def _clamp(text: str, max_chars: int) -> str:
    value = (text or "").strip()
    if max_chars <= 0 or len(value) <= max_chars:
        return value
    return value[: max(0, max_chars - 1)].rstrip() + "…"


def _hashtags(keywords: list[str], *, limit: int = 8) -> list[str]:
    tags: list[str] = []
    for kw in keywords:
        raw = _HASH_RE.sub("", (kw or "").strip())
        if not raw:
            continue
        tag = f"#{raw}" if not raw.startswith("#") else raw
        if tag not in tags:
            tags.append(tag)
        if len(tags) >= limit:
            break
    return tags


def _pick_aspect(
    preset: PlatformPreset,
    *,
    reframe_aspect: str,
    video_type_aspect: str,
) -> tuple[str, list[str]]:
    warnings: list[str] = []
    supported = list(preset.supported_aspect_ratios) or ["9:16"]
    for candidate in (reframe_aspect, video_type_aspect):
        c = (candidate or "").strip()
        if c and c in supported:
            return c, warnings
    # Prefer first supported
    chosen = supported[0]
    if reframe_aspect and reframe_aspect not in supported:
        warnings.append(
            f"Reframe aspect '{reframe_aspect}' not in {preset.name} supported "
            f"{supported}; recommending '{chosen}'."
        )
    return chosen, warnings


def build_platform_pack(
    platform_label: str,
    *,
    project_id: str,
    enabled: bool = True,
    scripts: dict[str, Any] | None = None,
    localizations: dict[str, Any] | None = None,
    video_type_pack: dict[str, Any] | None = None,
    captions_pack: dict[str, Any] | None = None,
    reframe_pack: dict[str, Any] | None = None,
) -> PlatformPack:
    label = (platform_label or "").strip() or "YouTube Shorts"
    preset, fallback = resolve_or_fallback(label)
    preset.publish_enabled = False

    if not enabled:
        plan = PlatformPlan(
            project_id=project_id,
            platform_name=preset.name,
            skipped=True,
            export_hints=PlatformExportHints(
                preferred_aspect=(preset.supported_aspect_ratios or ["9:16"])[0],
                official_url=preset.official_url,
                publish_enabled=False,
                publish_status="not_published",
            ),
            notes="Platform optimization feature flag off — skipped.",
        )
        return PlatformPack(
            source_label=label,
            preset=preset,
            plan=plan,
            fallback=fallback,
            notes=plan.notes,
        )

    script = _localized_script(localizations) or _first_script(scripts)
    title = str(script.get("title") or "").strip()
    hook = str(script.get("hook") or "").strip()
    caption = str(script.get("caption") or script.get("short_script") or "").strip()
    cta = str(script.get("cta") or "").strip() or preset.cta_strategy
    thumb = str(script.get("thumbnail_text") or "").strip()
    keywords = script.get("keywords") or []
    if not isinstance(keywords, list):
        keywords = []
    keywords_s = [str(k) for k in keywords]

    title_req = preset.title_requirements
    max_title = int(title_req.max_chars or 0)
    warnings: list[str] = []

    if title_req.required and not title:
        title = hook or caption.split(".")[0] if caption else preset.name
        warnings.append("Title was empty — derived from hook/caption.")
    if max_title > 0 and len(title) > max_title:
        warnings.append(
            f"Title exceeds {max_title} chars for {preset.name}; clamped."
        )
    title = _clamp(title, max_title) if max_title > 0 else title

    # Caption length soft clamp (~2200 IG-like when behavior mentions max)
    caption_out = caption or hook
    if "2200" in (preset.caption_behavior or ""):
        caption_out = _clamp(caption_out, 2200)
    if max_title > 0 and preset.name == "X":
        # Post body is the title/body
        caption_out = _clamp(caption or title, max_title)

    description = caption_out
    if "description" in (preset.metadata_requirements or []):
        description = caption_out or hook

    reframe_aspect = ""
    if isinstance(reframe_pack, dict):
        plan = reframe_pack.get("plan") or {}
        if isinstance(plan, dict):
            reframe_aspect = str(plan.get("target_aspect") or "")
    vt_aspect = ""
    if isinstance(video_type_pack, dict):
        preset_vt = video_type_pack.get("preset") or {}
        if isinstance(preset_vt, dict):
            vt_aspect = str(preset_vt.get("aspect_ratio") or "")

    aspect, aspect_warnings = _pick_aspect(
        preset, reframe_aspect=reframe_aspect, video_type_aspect=vt_aspect
    )
    warnings.extend(aspect_warnings)

    if preset.subreddit_dependent:
        warnings.append(
            "Reddit is subreddit-dependent — match community rules before posting "
            "(manual; no auto-publish)."
        )

    burn_in = True
    if isinstance(captions_pack, dict):
        cplan = captions_pack.get("plan") or {}
        if isinstance(cplan, dict) and cplan.get("burn_in_applied"):
            burn_in = True
        style = captions_pack.get("style") or {}
        if isinstance(style, dict) and style.get("animation") == "none":
            burn_in = True

    safe = SafeTextArea(
        margin_l=preset.safe_text_area.margin_l,
        margin_r=preset.safe_text_area.margin_r,
        margin_v=preset.safe_text_area.margin_v,
    )

    metadata = PlatformMetadata(
        title=title,
        description=description,
        caption=caption_out,
        hashtags=_hashtags(keywords_s),
        cta=cta,
        tags=keywords_s[:12],
        aspect_recommendation=aspect,
        duration_recommendation=preset.recommended_duration_seconds,
        hook=hook or title,
        thumbnail_text=thumb or _clamp(title, 40),
        warnings=warnings,
    )
    export_hints = PlatformExportHints(
        preferred_aspect=aspect,
        caption_burn_in=burn_in,
        safe_margins=safe,
        file_naming=f"{project_id}_{preset.id}_{aspect.replace(':', 'x')}",
        publish_status="not_published",
        official_url=preset.official_url,
        publish_enabled=False,
    )

    plan = PlatformPlan(
        project_id=project_id,
        platform_name=preset.name,
        skipped=False,
        metadata=metadata,
        export_hints=export_hints,
        notes=(
            f"Optimized metadata for {preset.name}. "
            "Opening official_url is not publishing; "
            "API/OAuth publishing is out of scope."
        ),
    )
    return PlatformPack(
        source_label=label,
        preset=preset,
        plan=plan,
        fallback=fallback,
        notes=plan.notes,
    )
