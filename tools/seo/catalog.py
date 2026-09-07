"""Load and resolve SEO presets from config/seo.json."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from schemas.job import VideoJobConfig
from schemas.seo import SeoPack, SeoPlan, SeoPreset

_CATALOG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "seo.json"

_STOP = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "to",
    "of",
    "in",
    "on",
    "for",
    "with",
    "this",
    "that",
    "is",
    "are",
    "be",
    "you",
    "your",
}


def _norm(value: str) -> str:
    return " ".join(
        (value or "").strip().lower().replace("_", " ").replace("-", " ").split()
    )


@lru_cache(maxsize=1)
def _load_raw() -> list[dict[str, Any]]:
    return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))


def clear_seo_cache() -> None:
    _load_raw.cache_clear()


def list_seo_presets() -> list[SeoPreset]:
    return [SeoPreset.model_validate(item) for item in _load_raw()]


def resolve_seo(name_or_id: str) -> SeoPreset | None:
    key = _norm(name_or_id)
    if not key:
        return None
    for preset in list_seo_presets():
        if _norm(preset.id) == key or _norm(preset.name) == key:
            return preset
        for alias in preset.aliases:
            if _norm(alias) == key:
                return preset
    for preset in list_seo_presets():
        pname = _norm(preset.name)
        if pname and (key.startswith(pname) or pname in key):
            return preset
    return None


def _fallback_youtube(label: str) -> SeoPreset:
    yt = resolve_seo("YouTube")
    if yt is not None:
        return yt.model_copy(
            update={"notes": f"Unknown platform '{label}' — falling back to YouTube."}
        )
    return SeoPreset(
        id="youtube",
        name="YouTube",
        max_title_chars=100,
        max_description_chars=5000,
        notes=f"Unknown platform '{label}' — falling back to YouTube.",
    )


def _first_nonempty(*values: str) -> str:
    for v in values:
        s = (v or "").strip()
        if s:
            return s
    return ""


def _clamp(text: str, max_chars: int) -> str:
    t = (text or "").strip()
    if max_chars <= 0 or len(t) <= max_chars:
        return t
    return t[: max(0, max_chars - 1)].rstrip() + "…"


def _as_list(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    if isinstance(raw, str) and raw.strip():
        return [p.strip() for p in re.split(r"[,;#]+", raw) if p.strip()]
    return []


def _tagify(items: list[str], *, hashed: bool, limit: int) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        raw = item.strip()
        if not raw:
            continue
        if hashed:
            body = raw.lstrip("#").replace(" ", "")
            if not body:
                continue
            val = f"#{body}"
        else:
            val = raw.lstrip("#").strip()
            if not val:
                continue
        key = _norm(val)
        if key in seen:
            continue
        seen.add(key)
        out.append(val)
        if len(out) >= limit:
            break
    return out


def _tokens_from_text(text: str, limit: int) -> list[str]:
    words = re.findall(r"[A-Za-z0-9']+", text or "")
    out: list[str] = []
    seen: set[str] = set()
    for w in words:
        key = w.lower()
        if key in _STOP or len(key) < 3:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(w)
        if len(out) >= limit:
            break
    return out


def _dig_str(obj: Any, *keys: str) -> str:
    cur: Any = obj
    for key in keys:
        if not isinstance(cur, dict):
            return ""
        cur = cur.get(key)
    return str(cur or "").strip() if cur is not None else ""


def _extract_source(
    script_pack: dict[str, Any] | None,
    platform_pack: dict[str, Any] | None,
) -> tuple[str, str, list[str], list[str], list[str]]:
    title = ""
    description = ""
    tags: list[str] = []
    hashtags: list[str] = []
    keywords: list[str] = []

    if isinstance(platform_pack, dict):
        plan = platform_pack.get("plan") or {}
        meta = plan.get("metadata") if isinstance(plan, dict) else {}
        if isinstance(meta, dict):
            title = _first_nonempty(title, str(meta.get("title") or ""))
            description = _first_nonempty(
                description,
                str(meta.get("description") or ""),
                str(meta.get("caption") or ""),
                str(meta.get("hook") or ""),
            )
            tags.extend(_as_list(meta.get("tags")))
            hashtags.extend(_as_list(meta.get("hashtags")))
            keywords.extend(_as_list(meta.get("keywords")))

    if isinstance(script_pack, dict):
        for path in (
            ("plan", "title"),
            ("plan", "hook"),
            ("title",),
            ("hook",),
        ):
            val = _dig_str(script_pack, *path)
            if path[-1] == "title":
                title = _first_nonempty(title, val)
            elif path[-1] == "hook":
                description = _first_nonempty(description, val)

        for key in ("tags", "hashtags", "keywords"):
            raw = script_pack.get(key)
            if key == "tags":
                tags.extend(_as_list(raw))
            elif key == "hashtags":
                hashtags.extend(_as_list(raw))
            else:
                keywords.extend(_as_list(raw))

        plan = script_pack.get("plan")
        if isinstance(plan, dict):
            tags.extend(_as_list(plan.get("tags")))
            hashtags.extend(_as_list(plan.get("hashtags")))
            keywords.extend(_as_list(plan.get("keywords")))
            description = _first_nonempty(
                description,
                str(plan.get("description") or ""),
                str(plan.get("caption") or ""),
            )

        scripts = script_pack.get("scripts") or script_pack.get("items")
        if isinstance(scripts, list) and scripts and isinstance(scripts[0], dict):
            first = scripts[0]
            title = _first_nonempty(title, str(first.get("title") or ""))
            description = _first_nonempty(
                description,
                str(first.get("hook") or ""),
                str(first.get("description") or ""),
            )
            tags.extend(_as_list(first.get("tags")))
            hashtags.extend(_as_list(first.get("hashtags")))
            keywords.extend(_as_list(first.get("keywords")))

        primary = script_pack.get("primary") or script_pack.get("script")
        if isinstance(primary, dict):
            title = _first_nonempty(title, str(primary.get("title") or ""))
            description = _first_nonempty(
                description,
                str(primary.get("hook") or ""),
                str(primary.get("description") or ""),
            )
            tags.extend(_as_list(primary.get("tags")))
            hashtags.extend(_as_list(primary.get("hashtags")))
            keywords.extend(_as_list(primary.get("keywords")))

    return title, description, tags, hashtags, keywords


def build_seo_pack(
    platform_label: str,
    *,
    enabled: bool = True,
    config: VideoJobConfig | None = None,
    script_pack: dict[str, Any] | None = None,
    platform_pack: dict[str, Any] | None = None,
    brand_pack: dict[str, Any] | None = None,
    shared_ai: dict[str, Any] | None = None,
) -> SeoPack:
    job = config or VideoJobConfig()
    explicit = (getattr(job, "seo_platform", None) or "").strip()
    label = (
        explicit
        or (platform_label or "").strip()
        or (job.platform or "").strip()
        or "YouTube"
    )

    preset = resolve_seo(label)
    fallback = False
    if preset is None:
        preset = _fallback_youtube(label)
        fallback = True

    if not enabled:
        plan = SeoPlan(
            platform=preset.name,
            skipped=True,
            notes="SEO feature flag off — skipped.",
        )
        return SeoPack(
            source_label=label,
            preset=preset,
            plan=plan,
            fallback=fallback,
            notes=plan.notes,
        )

    title, description, tags_raw, hash_raw, kw_raw = _extract_source(
        script_pack, platform_pack
    )
    if isinstance(shared_ai, dict):
        seeds = shared_ai.get("seo_seeds") or {}
        if isinstance(seeds, dict):
            title = title or str(seeds.get("title") or "")
            description = description or str(seeds.get("description") or "")
            for key, bucket in (
                ("tags", tags_raw),
                ("keywords", kw_raw),
                ("hashtags", hash_raw),
            ):
                extra = seeds.get(key) or []
                if isinstance(extra, list):
                    bucket.extend(str(x) for x in extra if x)
    if not title:
        title = _first_nonempty(description, f"{preset.name} video tips")
    if not description:
        description = _first_nonempty(title, "Watch now for more.")

    title = _clamp(title, preset.max_title_chars)
    description = _clamp(description, preset.max_description_chars)

    tags = _tagify(tags_raw + kw_raw + _tokens_from_text(title, 8), hashed=False, limit=preset.max_tags)
    keywords = _tagify(
        kw_raw + tags_raw + _tokens_from_text(f"{title} {description}", 12),
        hashed=False,
        limit=preset.max_keywords,
    )
    hashtags = _tagify(
        hash_raw + tags + keywords,
        hashed=True,
        limit=preset.max_hashtags,
    )
    # Ensure at least 2 hashtags when we have source text
    if len(hashtags) < 2 and title:
        extra = _tagify(_tokens_from_text(title, 6), hashed=True, limit=preset.max_hashtags)
        hashtags = _tagify(hashtags + extra, hashed=True, limit=preset.max_hashtags)
    if not keywords and title:
        keywords = _tagify(_tokens_from_text(title, preset.max_keywords), hashed=False, limit=preset.max_keywords)

    from tools.brand.catalog import brand_constraint_notes

    brand_notes = brand_constraint_notes(brand_pack)
    plan = SeoPlan(
        title=title,
        description=description,
        tags=tags,
        hashtags=hashtags,
        keywords=keywords,
        platform=preset.name,
        skipped=False,
        notes=(
            f"SEO planned for {preset.name}. "
            f"title≤{preset.max_title_chars} desc≤{preset.max_description_chars} "
            f"hashtags≤{preset.max_hashtags}. Plan only (MVP)."
            + (f" Brand: {brand_notes}." if brand_notes else "")
        ),
    )
    return SeoPack(
        source_label=label,
        preset=preset,
        plan=plan,
        fallback=fallback,
        notes=plan.notes,
    )
