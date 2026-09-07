"""Load and resolve thumbnail presets from config/thumbnails.json."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from schemas.job import VideoJobConfig
from schemas.thumbnail import ThumbnailPack, ThumbnailPlan, ThumbnailPreset

_CATALOG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "thumbnails.json"

_FACE_PLACEMENT: dict[str, str] = {
    "left_third": "Place face in left third; keep eyes above horizontal midline.",
    "right_third": "Place face in right third; leave left for text.",
    "center": "Center face; leave bottom band clear for overlay text.",
    "upper_third": "Face in upper third; bold text centered mid-frame.",
}


def _norm(value: str) -> str:
    return " ".join(
        (value or "").strip().lower().replace("_", " ").replace("-", " ").split()
    )


@lru_cache(maxsize=1)
def _load_raw() -> list[dict[str, Any]]:
    return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))


def clear_thumbnail_cache() -> None:
    _load_raw.cache_clear()


def list_thumbnails() -> list[ThumbnailPreset]:
    return [ThumbnailPreset.model_validate(item) for item in _load_raw()]


def resolve_thumbnail(name_or_id: str) -> ThumbnailPreset | None:
    key = _norm(name_or_id)
    if not key:
        return None
    for preset in list_thumbnails():
        if _norm(preset.id) == key or _norm(preset.name) == key:
            return preset
        for alias in preset.aliases:
            if _norm(alias) == key:
                return preset
    # Soft map: "youtube shorts" → youtube by prefix token
    for preset in list_thumbnails():
        pname = _norm(preset.name)
        if key.startswith(pname) or pname.startswith(key.split()[0] if key else ""):
            if pname and (pname in key or key.startswith(pname)):
                return preset
    return None


def _fallback_youtube(label: str) -> ThumbnailPreset:
    yt = resolve_thumbnail("YouTube")
    if yt is not None:
        return yt
    return ThumbnailPreset(
        id="youtube",
        name="YouTube",
        layout="face_left_text_right",
        face_zone="left_third",
        aspect_hint="16:9",
        default_emotion="curious",
        notes=f"Unknown platform '{label}' — falling back to YouTube.",
    )


def _dig_str(obj: Any, *keys: str) -> str:
    cur: Any = obj
    for key in keys:
        if not isinstance(cur, dict):
            return ""
        cur = cur.get(key)
    return str(cur or "").strip() if cur is not None else ""


def _first_nonempty(*values: str) -> str:
    for v in values:
        s = (v or "").strip()
        if s:
            return s
    return ""


def _truncate_words(text: str, max_words: int) -> str:
    words = re.findall(r"\S+", (text or "").strip())
    if not words:
        return ""
    return " ".join(words[:max_words])


def _extract_text_fields(
    script_pack: dict[str, Any] | None,
    platform_pack: dict[str, Any] | None,
    viral_pack: dict[str, Any] | None,
    seo_pack: dict[str, Any] | None = None,
    trend_pack: dict[str, Any] | None = None,
) -> tuple[str, str, str]:
    """Prefer SEO → trend topics → platform → scripts → viral; never invent timing."""
    title = ""
    hook = ""
    thumb = ""

    if isinstance(seo_pack, dict):
        plan = seo_pack.get("plan") or {}
        if isinstance(plan, dict) and not plan.get("skipped"):
            title = _first_nonempty(title, str(plan.get("title") or ""))
            hook = _first_nonempty(
                hook,
                str(plan.get("description") or ""),
                str(plan.get("title") or ""),
            )

    if isinstance(trend_pack, dict):
        plan = trend_pack.get("plan") or {}
        if isinstance(plan, dict) and not plan.get("skipped"):
            topics = plan.get("trend_topics") or []
            if isinstance(topics, list) and topics:
                seed = str(topics[0] or "").strip()
                title = _first_nonempty(title, seed)
                hook = _first_nonempty(hook, seed)

    if isinstance(platform_pack, dict):
        plan = platform_pack.get("plan") or {}
        meta = plan.get("metadata") if isinstance(plan, dict) else {}
        if isinstance(meta, dict):
            title = _first_nonempty(title, str(meta.get("title") or ""))
            hook = _first_nonempty(hook, str(meta.get("hook") or ""))
            thumb = _first_nonempty(thumb, str(meta.get("thumbnail_text") or ""))

    if isinstance(script_pack, dict):
        # scripts pack may nest primary script under plan / scripts / clips
        for path in (
            ("plan", "title"),
            ("plan", "hook"),
            ("plan", "thumbnail_text"),
            ("title",),
            ("hook",),
            ("thumbnail_text",),
        ):
            val = _dig_str(script_pack, *path)
            if path[-1] == "title":
                title = _first_nonempty(title, val)
            elif path[-1] == "hook":
                hook = _first_nonempty(hook, val)
            elif path[-1] == "thumbnail_text":
                thumb = _first_nonempty(thumb, val)

        scripts = script_pack.get("scripts") or script_pack.get("items")
        if isinstance(scripts, list) and scripts:
            first = scripts[0] if isinstance(scripts[0], dict) else {}
            if isinstance(first, dict):
                title = _first_nonempty(title, str(first.get("title") or ""))
                hook = _first_nonempty(hook, str(first.get("hook") or ""))
                thumb = _first_nonempty(
                    thumb, str(first.get("thumbnail_text") or "")
                )

        primary = script_pack.get("primary") or script_pack.get("script")
        if isinstance(primary, dict):
            title = _first_nonempty(title, str(primary.get("title") or ""))
            hook = _first_nonempty(hook, str(primary.get("hook") or ""))
            thumb = _first_nonempty(
                thumb, str(primary.get("thumbnail_text") or "")
            )

    if isinstance(viral_pack, dict):
        moments = viral_pack.get("moments") or viral_pack.get("items") or []
        if isinstance(moments, list) and moments:
            m0 = moments[0] if isinstance(moments[0], dict) else {}
            if isinstance(m0, dict):
                title = _first_nonempty(
                    title, str(m0.get("suggested_title") or m0.get("title") or "")
                )
                hook = _first_nonempty(hook, str(m0.get("hook") or ""))

    return title, hook, thumb


def _click_titles(title: str, hook: str, thumb: str) -> list[str]:
    base = _first_nonempty(title, hook, thumb, "Watch This")
    variants = [
        base,
        f"{base}?" if not base.endswith("?") else base,
        f"You Won't Believe: {_truncate_words(base, 6)}"
        if len(base.split()) > 2
        else f"Must See: {base}",
        f"STOP Scrolling — {_truncate_words(base, 5)}",
        f"{_truncate_words(base, 4)} (Explained)",
    ]
    # Dedupe preserving order
    out: list[str] = []
    seen: set[str] = set()
    for v in variants:
        key = _norm(v)
        if key and key not in seen:
            seen.add(key)
            out.append(v.strip())
    return out


def _ctr_score(title: str, *, emotion: str = "", hook: str = "") -> float:
    """Heuristic CTR score for ranking thumbnail text variants."""
    t = (title or "").strip()
    if not t:
        return 0.0
    score = 0.35
    words = t.split()
    n = len(words)
    if 3 <= n <= 8:
        score += 0.2
    elif n <= 12:
        score += 0.1
    lower = t.lower()
    for token, boost in (
        ("?", 0.12),
        ("you", 0.08),
        ("won", 0.1),
        ("stop", 0.08),
        ("secret", 0.1),
        ("must", 0.06),
        ("explained", 0.05),
    ):
        if token in lower:
            score += boost
    if emotion and emotion.lower() not in {"neutral", ""}:
        score += 0.08
    if hook and _norm(hook) in _norm(t):
        score += 0.05
    if t[:1].isupper():
        score += 0.03
    return round(min(1.0, score), 4)


def rank_thumbnail_titles(
    titles: list[str],
    *,
    emotion: str = "",
    hook: str = "",
    limit: int = 3,
) -> list[str]:
    """Return top-N titles by heuristic CTR score."""
    scored = [
        (_ctr_score(t, emotion=emotion, hook=hook), t) for t in titles if (t or "").strip()
    ]
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [t for _, t in scored[: max(0, limit)]]


def _emotion(
    config: VideoJobConfig,
    preset: ThumbnailPreset,
    viral_pack: dict[str, Any] | None,
) -> str:
    voice_em = (getattr(config, "voice_emotion", None) or "").strip()
    if voice_em and voice_em.lower() not in {"neutral", ""}:
        return voice_em
    if isinstance(viral_pack, dict):
        moments = viral_pack.get("moments") or []
        if isinstance(moments, list) and moments and isinstance(moments[0], dict):
            score = moments[0].get("scores") or {}
            if isinstance(score, dict) and float(score.get("hook") or 0) >= 0.7:
                return "excited"
    return preset.default_emotion or "curious"


def build_thumbnail_pack(
    platform_label: str,
    *,
    enabled: bool = True,
    config: VideoJobConfig | None = None,
    script_pack: dict[str, Any] | None = None,
    platform_pack: dict[str, Any] | None = None,
    viral_pack: dict[str, Any] | None = None,
    seo_pack: dict[str, Any] | None = None,
    trend_pack: dict[str, Any] | None = None,
    brand_pack: dict[str, Any] | None = None,
    shared_ai: dict[str, Any] | None = None,
) -> ThumbnailPack:
    job = config or VideoJobConfig()
    # Prefer explicit thumbnail_platform, else platform_label, else job.platform
    explicit = (getattr(job, "thumbnail_platform", None) or "").strip()
    label = (
        explicit
        or (platform_label or "").strip()
        or (job.platform or "").strip()
        or "YouTube"
    )

    preset = resolve_thumbnail(label)
    fallback = False
    if preset is None:
        preset = _fallback_youtube(label)
        fallback = True

    if not enabled:
        plan = ThumbnailPlan(
            title="",
            hook="",
            thumbnail_text="",
            emotion="",
            layout="",
            face_placement="",
            click_titles=[],
            platform=preset.name,
            skipped=True,
            notes="Thumbnail feature flag off — skipped.",
        )
        return ThumbnailPack(
            source_label=label,
            preset=preset,
            plan=plan,
            fallback=fallback,
            notes=plan.notes,
        )

    title, hook, thumb = _extract_text_fields(
        script_pack,
        platform_pack,
        viral_pack,
        seo_pack=seo_pack,
        trend_pack=trend_pack,
    )
    if isinstance(shared_ai, dict):
        seeds = shared_ai.get("seo_seeds") or {}
        hooks = shared_ai.get("hooks") or []
        if isinstance(seeds, dict):
            title = _first_nonempty(title, str(seeds.get("title") or ""))
            thumb = _first_nonempty(thumb, str(seeds.get("title") or ""))
        if isinstance(hooks, list) and hooks:
            hook = _first_nonempty(hook, str(hooks[0] or ""))
    if not title:
        title = _first_nonempty(hook, thumb, f"{preset.name} Must Watch")
    if not hook:
        hook = _first_nonempty(title, "Wait for it…")
    if not thumb:
        thumb = _truncate_words(title, 4) or "WATCH"

    emotion = _emotion(job, preset, viral_pack)
    face = _FACE_PLACEMENT.get(
        preset.face_zone,
        f"Place subject in {preset.face_zone or 'center'}.",
    )
    raw_clicks = _click_titles(title, hook, thumb)
    try:
        from config.settings import get_settings

        limit = int(get_settings().thumbnail_max_variants or 3)
    except Exception:  # noqa: BLE001
        limit = 3
    clicks = rank_thumbnail_titles(
        raw_clicks, emotion=emotion, hook=hook, limit=max(1, limit)
    )

    from tools.brand.catalog import brand_constraint_notes

    brand_notes = brand_constraint_notes(brand_pack)
    plan = ThumbnailPlan(
        title=title,
        hook=hook,
        thumbnail_text=thumb,
        emotion=emotion,
        layout=preset.layout,
        face_placement=face,
        click_titles=clicks,
        platform=preset.name,
        skipped=False,
        notes=(
            f"Thumbnail planned for {preset.name} ({preset.aspect_hint}). "
            f"layout={preset.layout} face_zone={preset.face_zone}. "
            f"Top {len(clicks)} CTR-ranked titles. "
            "Plan only — frame extract remains in Render (MVP)."
            + (f" Brand: {brand_notes}." if brand_notes else "")
            + (" Shared AI seeds applied." if shared_ai else "")
        ),
    )
    return ThumbnailPack(
        source_label=label,
        preset=preset,
        plan=plan,
        fallback=fallback,
        notes=plan.notes,
    )
