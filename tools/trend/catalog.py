"""Trend seed catalog and pack builder (Gemini + heuristic fallback)."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

from config.settings import get_settings
from schemas.job import VideoJobConfig
from schemas.trend import GeminiTrendAnalysis, TrendPack, TrendPlan

_CATALOG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "trends.json"

AnalyzeFn = Callable[..., GeminiTrendAnalysis]


def _norm(value: str) -> str:
    return " ".join(
        (value or "").strip().lower().replace("_", " ").replace("-", " ").split()
    )


@lru_cache(maxsize=1)
def _load_raw() -> list[dict[str, Any]]:
    return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))


def clear_trend_cache() -> None:
    _load_raw.cache_clear()


def list_trend_presets() -> list[dict[str, Any]]:
    return list(_load_raw())


def resolve_trend_preset(name_or_id: str) -> dict[str, Any] | None:
    key = _norm(name_or_id)
    if not key:
        return None
    for item in list_trend_presets():
        if _norm(str(item.get("id") or "")) == key or _norm(str(item.get("name") or "")) == key:
            return item
        for alias in item.get("aliases") or []:
            if _norm(str(alias)) == key:
                return item
    for item in list_trend_presets():
        pname = _norm(str(item.get("name") or ""))
        if pname and (key.startswith(pname) or pname in key):
            return item
    return None


def _fallback_youtube() -> dict[str, Any]:
    return resolve_trend_preset("YouTube") or {
        "id": "youtube",
        "name": "YouTube",
        "seed_topics": ["shorts tips"],
        "seed_hashtags": ["#shorts", "#viral"],
        "seed_keywords": ["tutorial"],
        "viral_patterns": ["hook in 3 seconds"],
    }


def _as_list(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    if isinstance(raw, str) and raw.strip():
        return [p.strip() for p in re.split(r"[,;]+", raw) if p.strip()]
    return []


def _dedupe(items: list[str], *, limit: int = 8) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = _norm(item)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item.strip())
        if len(out) >= limit:
            break
    return out


def _clamp_score(value: float) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        score = 0.0
    return max(0.0, min(100.0, round(score, 1)))


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in re.findall(r"[A-Za-z0-9']+", text or "") if len(t) > 2}


def _gather_signals(
    script_pack: dict[str, Any] | None,
    platform_pack: dict[str, Any] | None,
    seo_pack: dict[str, Any] | None,
    viral_pack: dict[str, Any] | None,
) -> dict[str, Any]:
    title = ""
    description = ""
    tags: list[str] = []
    hashtags: list[str] = []
    keywords: list[str] = []
    viral_hooks: list[str] = []

    if isinstance(seo_pack, dict):
        plan = seo_pack.get("plan") or {}
        if isinstance(plan, dict) and not plan.get("skipped"):
            title = str(plan.get("title") or title)
            description = str(plan.get("description") or description)
            tags.extend(_as_list(plan.get("tags")))
            hashtags.extend(_as_list(plan.get("hashtags")))
            keywords.extend(_as_list(plan.get("keywords")))

    if isinstance(platform_pack, dict):
        plan = platform_pack.get("plan") or {}
        meta = plan.get("metadata") if isinstance(plan, dict) else {}
        if isinstance(meta, dict):
            title = title or str(meta.get("title") or "")
            description = description or str(
                meta.get("description") or meta.get("hook") or ""
            )
            tags.extend(_as_list(meta.get("tags")))
            hashtags.extend(_as_list(meta.get("hashtags")))
            keywords.extend(_as_list(meta.get("keywords")))

    if isinstance(script_pack, dict):
        primary = script_pack.get("primary") or script_pack.get("script")
        if isinstance(primary, dict):
            title = title or str(primary.get("title") or "")
            description = description or str(primary.get("hook") or "")
            tags.extend(_as_list(primary.get("tags")))
            keywords.extend(_as_list(primary.get("keywords")))
        scripts = script_pack.get("scripts") or script_pack.get("items")
        if isinstance(scripts, list) and scripts and isinstance(scripts[0], dict):
            first = scripts[0]
            title = title or str(first.get("title") or "")
            description = description or str(first.get("hook") or "")

    if isinstance(viral_pack, dict):
        moments = viral_pack.get("moments") or viral_pack.get("items") or []
        if isinstance(moments, list):
            for m in moments[:5]:
                if not isinstance(m, dict):
                    continue
                hook = str(m.get("hook") or m.get("suggested_title") or m.get("title") or "")
                if hook:
                    viral_hooks.append(hook)

    return {
        "title": title.strip(),
        "description": description.strip(),
        "tags": _dedupe(tags),
        "hashtags": _dedupe(hashtags),
        "keywords": _dedupe(keywords),
        "viral_hooks": _dedupe(viral_hooks),
    }


def _heuristic_analysis(
    preset: dict[str, Any],
    signals: dict[str, Any],
) -> GeminiTrendAnalysis:
    seed_topics = _as_list(preset.get("seed_topics"))
    seed_hash = _as_list(preset.get("seed_hashtags"))
    seed_kw = _as_list(preset.get("seed_keywords"))
    patterns = _as_list(preset.get("viral_patterns"))

    blob = " ".join(
        [
            signals.get("title") or "",
            signals.get("description") or "",
            " ".join(signals.get("tags") or []),
            " ".join(signals.get("keywords") or []),
            " ".join(signals.get("viral_hooks") or []),
        ]
    )
    toks = _tokens(blob)

    matched_topics: list[str] = []
    for topic in seed_topics:
        t_toks = _tokens(topic)
        if t_toks & toks or not toks:
            matched_topics.append(topic)

    if not matched_topics:
        matched_topics = seed_topics[:3]

    overlap = 0
    for kw in seed_kw + seed_topics:
        if _tokens(kw) & toks:
            overlap += 1
    viral_bonus = 15.0 if signals.get("viral_hooks") else 0.0
    score = min(100.0, 35.0 + overlap * 12.0 + viral_bonus)

    tags = _dedupe(
        list(signals.get("tags") or [])
        + [t.lstrip("#") for t in seed_hash]
        + seed_kw
        + matched_topics,
        limit=8,
    )
    hashtags = _dedupe(
        list(signals.get("hashtags") or [])
        + [h if h.startswith("#") else f"#{h.lstrip('#')}" for h in seed_hash],
        limit=8,
    )
    keywords = _dedupe(
        list(signals.get("keywords") or []) + seed_kw + matched_topics,
        limit=8,
    )

    return GeminiTrendAnalysis(
        trend_score=score,
        trend_topics=matched_topics[:6],
        recommended_tags=tags,
        trending_hashtags=hashtags,
        trending_keywords=keywords,
        viral_patterns=patterns[:5],
        audience_relevance=(
            f"Heuristic match for {preset.get('name')}: "
            f"{len(matched_topics)} topics, viral_hooks={len(signals.get('viral_hooks') or [])}."
        ),
        topic_labels=matched_topics[:4],
    )


def build_trend_pack(
    platform_label: str,
    *,
    enabled: bool = True,
    config: VideoJobConfig | None = None,
    script_pack: dict[str, Any] | None = None,
    platform_pack: dict[str, Any] | None = None,
    seo_pack: dict[str, Any] | None = None,
    viral_pack: dict[str, Any] | None = None,
    brand_pack: dict[str, Any] | None = None,
    analyze_fn: AnalyzeFn | None = None,
) -> TrendPack:
    job = config or VideoJobConfig()
    label = (platform_label or "").strip() or (job.platform or "").strip() or "YouTube"
    preset = resolve_trend_preset(label) or _fallback_youtube()
    platform_name = str(preset.get("name") or "YouTube")
    fallback = resolve_trend_preset(label) is None

    if not enabled:
        plan = TrendPlan(
            platform=platform_name,
            provider="none",
            skipped=True,
            notes="Trend feature flag off — skipped.",
        )
        return TrendPack(
            source_label=label,
            plan=plan,
            fallback=fallback,
            notes=plan.notes,
        )

    settings = get_settings()
    try:
        from tools.cache.trends import load_cached_trend, store_cached_trend

        ttl = float(settings.trend_cache_ttl_hours or 24) * 3600.0
        cached = load_cached_trend(
            label,
            script_pack=script_pack if isinstance(script_pack, dict) else None,
            seo_pack=seo_pack if isinstance(seo_pack, dict) else None,
            ttl_seconds=ttl,
        )
        if isinstance(cached, dict) and cached.get("plan"):
            try:
                pack = TrendPack.model_validate(cached)
                notes = pack.notes or ""
                if "cache hit" not in notes.lower():
                    pack = pack.model_copy(
                        update={"notes": f"{notes} (24h trend cache hit)".strip()}
                    )
                return pack
            except Exception:  # noqa: BLE001
                pass
    except Exception:  # noqa: BLE001
        pass

    signals = _gather_signals(script_pack, platform_pack, seo_pack, viral_pack)
    analysis: GeminiTrendAnalysis | None = None
    provider = "heuristic"
    notes_extra = ""

    use_gemini = bool(analyze_fn is not None or settings.has_gemini_api_key)
    if use_gemini:
        try:
            from tools.llm.gemini import analyze_trends

            fn = analyze_fn or analyze_trends
            seed_block = json.dumps(
                {
                    "seed_topics": preset.get("seed_topics"),
                    "seed_hashtags": preset.get("seed_hashtags"),
                    "seed_keywords": preset.get("seed_keywords"),
                    "viral_patterns": preset.get("viral_patterns"),
                },
                ensure_ascii=False,
            )
            analysis = fn(
                platform=platform_name,
                audience=job.audience or "General",
                title=signals["title"],
                description=signals["description"],
                tags=signals["tags"],
                hashtags=signals["hashtags"],
                keywords=signals["keywords"],
                viral_hooks=signals["viral_hooks"],
                seed_block=seed_block,
            )
            provider = "gemini"
        except Exception as exc:  # noqa: BLE001
            notes_extra = f" Gemini failed ({exc}); heuristic fallback."
            analysis = None
            provider = "heuristic"
            fallback = True

    if analysis is None:
        analysis = _heuristic_analysis(preset, signals)
        provider = "heuristic"
        fallback = True

    plan = TrendPlan(
        trend_score=_clamp_score(analysis.trend_score),
        trend_topics=_dedupe(list(analysis.trend_topics)),
        recommended_tags=_dedupe(
            [t.lstrip("#") for t in analysis.recommended_tags]
        ),
        trending_hashtags=_dedupe(
            [
                h if str(h).startswith("#") else f"#{str(h).lstrip('#')}"
                for h in analysis.trending_hashtags
            ]
        ),
        trending_keywords=_dedupe(list(analysis.trending_keywords)),
        viral_patterns=_dedupe(list(analysis.viral_patterns)),
        audience_relevance=(analysis.audience_relevance or "").strip(),
        topic_labels=_dedupe(list(analysis.topic_labels)),
        platform=platform_name,
        provider=provider,
        skipped=False,
        notes=(
            f"Trend analyzed for {platform_name} via {provider}."
            f"{notes_extra} Plan only (MVP)."
        ),
    )
    from tools.brand.catalog import brand_constraint_notes

    brand_notes = brand_constraint_notes(brand_pack)
    if brand_notes:
        plan = plan.model_copy(
            update={"notes": f"{plan.notes} Brand: {brand_notes}."}
        )
    pack = TrendPack(
        source_label=label,
        plan=plan,
        fallback=fallback,
        notes=plan.notes,
    )
    try:
        from tools.cache.trends import store_cached_trend

        store_cached_trend(
            label,
            pack.model_dump(mode="json"),
            script_pack=script_pack if isinstance(script_pack, dict) else None,
            seo_pack=seo_pack if isinstance(seo_pack, dict) else None,
        )
    except Exception:  # noqa: BLE001
        pass
    return pack
