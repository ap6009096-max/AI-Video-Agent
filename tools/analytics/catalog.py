"""Analytics prediction catalog and pack builder (Gemini + heuristic fallback)."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

from config.settings import get_settings
from schemas.analytics import (
    PREDICTION_DISCLAIMER,
    AnalyticsPack,
    AnalyticsPlan,
    GeminiAnalyticsAnalysis,
)
from schemas.job import VideoJobConfig

_CATALOG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "analytics.json"

AnalyzeFn = Callable[..., GeminiAnalyticsAnalysis]


@lru_cache(maxsize=1)
def _load_raw() -> dict[str, Any]:
    return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))


def clear_analytics_cache() -> None:
    _load_raw.cache_clear()


def _as_list(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    if isinstance(raw, str) and raw.strip():
        return [p.strip() for p in re.split(r"[,;]+", raw) if p.strip()]
    return []


def _dedupe(items: list[str], *, limit: int = 5) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = " ".join((item or "").strip().lower().split())
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


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _gather_signals(
    script_pack: dict[str, Any] | None,
    platform_pack: dict[str, Any] | None,
    seo_pack: dict[str, Any] | None,
    trend_pack: dict[str, Any] | None,
    repurpose_pack: dict[str, Any] | None,
    thumbnail_pack: dict[str, Any] | None,
    viral_pack: dict[str, Any] | None,
) -> dict[str, Any]:
    title = ""
    hook = ""
    description = ""
    tags: list[str] = []
    hashtags: list[str] = []
    keywords: list[str] = []
    trend_score = 0.0
    viral_final = 0.0
    viral_shareability = 0.0
    thumbnail_text = ""
    thumbnail_emotion = ""
    thumbnail_layout = ""

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
            hook = hook or str(meta.get("hook") or "")
            description = description or str(meta.get("description") or "")
            tags.extend(_as_list(meta.get("tags")))
            hashtags.extend(_as_list(meta.get("hashtags")))
            keywords.extend(_as_list(meta.get("keywords")))

    if isinstance(script_pack, dict):
        primary = script_pack.get("primary") or script_pack.get("script")
        if isinstance(primary, dict):
            title = title or str(primary.get("title") or "")
            hook = hook or str(primary.get("hook") or "")
            description = description or str(primary.get("summary") or "")
            tags.extend(_as_list(primary.get("tags")))
            keywords.extend(_as_list(primary.get("keywords")))
        scripts = script_pack.get("scripts") or script_pack.get("items")
        if isinstance(scripts, list) and scripts and isinstance(scripts[0], dict):
            first = scripts[0]
            title = title or str(first.get("title") or "")
            hook = hook or str(first.get("hook") or "")

    if isinstance(trend_pack, dict):
        plan = trend_pack.get("plan") or {}
        if isinstance(plan, dict) and not plan.get("skipped"):
            trend_score = _safe_float(plan.get("trend_score"))
            tags.extend(_as_list(plan.get("recommended_tags")))
            hashtags.extend(_as_list(plan.get("trending_hashtags")))
            keywords.extend(_as_list(plan.get("trending_keywords")))

    if isinstance(thumbnail_pack, dict):
        plan = thumbnail_pack.get("plan") or {}
        if isinstance(plan, dict) and not plan.get("skipped"):
            thumbnail_text = str(
                plan.get("thumbnail_text") or plan.get("title") or ""
            ).strip()
            thumbnail_emotion = str(plan.get("emotion") or "").strip()
            thumbnail_layout = str(plan.get("layout") or "").strip()
            title = title or str(plan.get("title") or "")
            hook = hook or str(plan.get("hook") or "")

    if isinstance(repurpose_pack, dict):
        plan = repurpose_pack.get("plan") or {}
        if isinstance(plan, dict) and not plan.get("skipped"):
            # Presence of multi-format pack slightly boosts shareability signals.
            if any(
                str(plan.get(k) or "").strip()
                for k in ("reels", "shorts", "tiktok", "linkedin_post")
            ):
                hashtags.extend(["#share"])

    if isinstance(viral_pack, dict):
        scores = viral_pack.get("scores") or {}
        if isinstance(scores, dict):
            viral_shareability = _safe_float(scores.get("shareability"))
            if viral_shareability <= 1.0:
                viral_shareability *= 100.0
        viral_final = _safe_float(viral_pack.get("final_score"))
        if viral_final <= 1.0 and viral_final > 0:
            viral_final *= 100.0
        # Nested report shape from ViralMomentsReport
        report = viral_pack.get("viral_moments") or viral_pack
        if isinstance(report, dict) and not viral_final:
            viral_final = _safe_float(report.get("final_score"))
            if viral_final <= 1.0 and viral_final > 0:
                viral_final *= 100.0
            scores = report.get("scores") or scores
            if isinstance(scores, dict):
                viral_shareability = _safe_float(scores.get("shareability")) or viral_shareability
                if viral_shareability <= 1.0 and viral_shareability > 0:
                    viral_shareability *= 100.0

    return {
        "title": title.strip(),
        "hook": hook.strip(),
        "description": description.strip(),
        "tags": _dedupe(tags, limit=8),
        "hashtags": _dedupe(hashtags, limit=8),
        "keywords": _dedupe(keywords, limit=8),
        "trend_score": _clamp_score(trend_score),
        "viral_final": _clamp_score(viral_final),
        "viral_shareability": _clamp_score(viral_shareability),
        "thumbnail_text": thumbnail_text,
        "thumbnail_emotion": thumbnail_emotion,
        "thumbnail_layout": thumbnail_layout,
    }


def _hook_strength(signals: dict[str, Any]) -> float:
    hook = str(signals.get("hook") or "")
    title = str(signals.get("title") or "")
    length = len(hook) or len(title)
    if length <= 0:
        return 20.0
    if length < 20:
        return 45.0
    if length < 80:
        return 70.0
    if length < 160:
        return 85.0
    return 60.0


def _seo_richness(signals: dict[str, Any]) -> float:
    n = (
        len(signals.get("tags") or [])
        + len(signals.get("hashtags") or [])
        + len(signals.get("keywords") or [])
    )
    if n <= 0:
        return 25.0
    return _clamp_score(30.0 + n * 6.0)


def _thumbnail_presence(signals: dict[str, Any]) -> float:
    score = 25.0
    if signals.get("thumbnail_text"):
        score += 35.0
    if signals.get("thumbnail_emotion"):
        score += 20.0
    if signals.get("thumbnail_layout"):
        score += 15.0
    return _clamp_score(score)


def _heuristic_analysis(
    catalog: dict[str, Any],
    signals: dict[str, Any],
) -> GeminiAnalyticsAnalysis:
    weights = catalog.get("weights") or {}
    offsets = catalog.get("score_offsets") or {}
    baseline = _safe_float(catalog.get("baseline"), 38.0)

    viral_share = _safe_float(signals.get("viral_shareability"))
    viral_final = _safe_float(signals.get("viral_final"))
    trend = _safe_float(signals.get("trend_score"))
    hook = _hook_strength(signals)
    seo = _seo_richness(signals)
    thumb = _thumbnail_presence(signals)

    blended = (
        baseline
        + viral_share * _safe_float(weights.get("viral_shareability"), 0.28)
        + viral_final * _safe_float(weights.get("viral_final"), 0.18)
        + trend * _safe_float(weights.get("trend_score"), 0.18)
        + hook * _safe_float(weights.get("hook_strength"), 0.14)
        + seo * _safe_float(weights.get("seo_richness"), 0.12)
        + thumb * _safe_float(weights.get("thumbnail_presence"), 0.10)
    ) / (
        1.0
        + _safe_float(weights.get("viral_shareability"), 0.28)
        + _safe_float(weights.get("viral_final"), 0.18)
        + _safe_float(weights.get("trend_score"), 0.18)
        + _safe_float(weights.get("hook_strength"), 0.14)
        + _safe_float(weights.get("seo_richness"), 0.12)
        + _safe_float(weights.get("thumbnail_presence"), 0.10)
    )
    # Re-scale toward 0–100 using component average
    components = [viral_share, viral_final, trend, hook, seo, thumb]
    present = [c for c in components if c > 0]
    core = sum(present) / len(present) if present else baseline

    engagement = _clamp_score(core + _safe_float(offsets.get("engagement")))
    retention = _clamp_score(
        0.55 * core + 0.45 * hook + _safe_float(offsets.get("retention"))
    )
    shareability = _clamp_score(
        0.5 * core
        + 0.35 * viral_share
        + 0.15 * trend
        + _safe_float(offsets.get("shareability"))
    )
    watch_time = _clamp_score(
        0.5 * retention + 0.3 * hook + 0.2 * core + _safe_float(offsets.get("watch_time"))
    )
    ctr = _clamp_score(
        0.45 * thumb + 0.35 * seo + 0.2 * core + _safe_float(offsets.get("ctr"))
    )

    return GeminiAnalyticsAnalysis(
        engagement_score=engagement,
        retention_score=retention,
        shareability_score=shareability,
        watch_time_score=watch_time,
        ctr_score=ctr,
        engagement_drivers=_dedupe(
            [
                f"hook_strength={hook:.0f}",
                f"trend_score={trend:.0f}",
                f"seo_richness={seo:.0f}",
            ]
        ),
        retention_drivers=_dedupe(
            [
                f"hook_strength={hook:.0f}",
                f"viral_final={viral_final:.0f}",
            ]
        ),
        shareability_drivers=_dedupe(
            [
                f"viral_shareability={viral_share:.0f}",
                f"trend_score={trend:.0f}",
            ]
        ),
        rationale=(
            f"Heuristic blend (core={core:.1f}, blended_hint={blended:.1f}). "
            f"{PREDICTION_DISCLAIMER}"
        ),
    )


def build_analytics_pack(
    platform_label: str,
    *,
    enabled: bool = True,
    config: VideoJobConfig | None = None,
    script_pack: dict[str, Any] | None = None,
    platform_pack: dict[str, Any] | None = None,
    seo_pack: dict[str, Any] | None = None,
    trend_pack: dict[str, Any] | None = None,
    repurpose_pack: dict[str, Any] | None = None,
    thumbnail_pack: dict[str, Any] | None = None,
    viral_pack: dict[str, Any] | None = None,
    analyze_fn: AnalyzeFn | None = None,
) -> AnalyticsPack:
    job = config or VideoJobConfig()
    label = (platform_label or "").strip() or (job.platform or "").strip() or "YouTube"
    platform_name = label
    catalog = _load_raw()
    fallback = False

    if not enabled:
        plan = AnalyticsPlan(
            platform=platform_name,
            provider="none",
            skipped=True,
            notes=f"Analytics feature flag off — skipped. {PREDICTION_DISCLAIMER}",
        )
        return AnalyticsPack(
            source_label=label,
            plan=plan,
            fallback=False,
            notes=plan.notes,
        )

    signals = _gather_signals(
        script_pack,
        platform_pack,
        seo_pack,
        trend_pack,
        repurpose_pack,
        thumbnail_pack,
        viral_pack,
    )
    analysis: GeminiAnalyticsAnalysis | None = None
    provider = "heuristic"
    notes_extra = ""

    settings = get_settings()
    use_gemini = bool(analyze_fn is not None or settings.has_gemini_api_key)
    if use_gemini:
        try:
            from tools.llm.gemini import analyze_analytics

            fn = analyze_fn or analyze_analytics
            weight_block = json.dumps(catalog.get("weights") or {}, ensure_ascii=False)
            analysis = fn(
                platform=platform_name,
                audience=job.audience or "General",
                title=signals["title"],
                hook=signals["hook"],
                description=signals["description"],
                tags=signals["tags"],
                hashtags=signals["hashtags"],
                keywords=signals["keywords"],
                trend_score=signals["trend_score"],
                viral_final=signals["viral_final"],
                viral_shareability=signals["viral_shareability"],
                thumbnail_text=signals["thumbnail_text"],
                thumbnail_emotion=signals["thumbnail_emotion"],
                thumbnail_layout=signals["thumbnail_layout"],
                weight_block=weight_block,
            )
            provider = "gemini"
        except Exception as exc:  # noqa: BLE001
            notes_extra = f" Gemini failed ({exc}); heuristic fallback."
            analysis = None
            provider = "heuristic"
            fallback = True

    if analysis is None:
        analysis = _heuristic_analysis(catalog, signals)
        provider = "heuristic"
        fallback = True

    plan = AnalyticsPlan(
        engagement_score=_clamp_score(analysis.engagement_score),
        retention_score=_clamp_score(analysis.retention_score),
        shareability_score=_clamp_score(analysis.shareability_score),
        watch_time_score=_clamp_score(analysis.watch_time_score),
        ctr_score=_clamp_score(analysis.ctr_score),
        engagement_drivers=_dedupe(list(analysis.engagement_drivers)),
        retention_drivers=_dedupe(list(analysis.retention_drivers)),
        shareability_drivers=_dedupe(list(analysis.shareability_drivers)),
        rationale=(analysis.rationale or "").strip() or PREDICTION_DISCLAIMER,
        platform=platform_name,
        provider=provider,
        skipped=False,
        notes=(
            f"Analytics predicted for {platform_name} via {provider}."
            f"{notes_extra} {PREDICTION_DISCLAIMER}"
        ),
    )
    return AnalyticsPack(
        source_label=label,
        plan=plan,
        fallback=fallback,
        notes=plan.notes,
    )
