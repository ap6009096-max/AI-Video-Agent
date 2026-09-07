"""Repurpose catalog + pack builder (Gemini + heuristic fallback)."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

from config.settings import get_settings
from schemas.job import SourceType, VideoJobConfig
from schemas.repurpose import GeminiRepurposeBatch, RepurposePack, RepurposePlan

_CATALOG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "repurpose.json"

AnalyzeFn = Callable[..., GeminiRepurposeBatch]

_KIND_ALIASES = {
    "video": "video",
    "podcast": "podcast",
    "article": "article",
    "transcript": "transcript",
    "youtube": "video",
    "upload": "video",
    "script": "transcript",
}


def _norm(value: str) -> str:
    return " ".join((value or "").strip().lower().replace("_", " ").split())


@lru_cache(maxsize=1)
def _load_raw() -> dict[str, Any]:
    return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))


def clear_repurpose_cache() -> None:
    _load_raw.cache_clear()


def format_hints() -> dict[str, Any]:
    raw = _load_raw()
    return dict(raw.get("formats") or {})


def resolve_source_kind(
    label: str,
    *,
    source_type: str | SourceType | None = None,
) -> str:
    key = _norm(label)
    if key in _KIND_ALIASES:
        return _KIND_ALIASES[key]
    if "podcast" in key:
        return "podcast"
    if "article" in key or "blog" in key:
        return "article"
    if "transcript" in key or "script" in key:
        return "transcript"
    if "video" in key or "youtube" in key or "upload" in key:
        return "video"

    st = source_type
    if isinstance(st, SourceType):
        st = st.value
    st_key = _norm(str(st or ""))
    if st_key in {"youtube", "upload"}:
        return "video"
    if st_key == "script":
        return "transcript"
    return "video"


def _clamp(text: str, max_chars: int) -> str:
    t = (text or "").strip()
    if max_chars <= 0 or len(t) <= max_chars:
        return t
    return t[: max(0, max_chars - 1)].rstrip() + "…"


def _as_list(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    if isinstance(raw, str) and raw.strip():
        return [p.strip() for p in re.split(r"[\n;]+", raw) if p.strip()]
    return []


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    return [p.strip() for p in parts if p.strip()]


def _dig_title_hook(script_pack: dict[str, Any] | None) -> tuple[str, str, str]:
    title = ""
    hook = ""
    body = ""
    if not isinstance(script_pack, dict):
        return title, hook, body
    primary = script_pack.get("primary") or script_pack.get("script")
    if isinstance(primary, dict):
        title = str(primary.get("title") or "")
        hook = str(primary.get("hook") or "")
        body = str(
            primary.get("short_script")
            or primary.get("caption")
            or primary.get("description")
            or ""
        )
    scripts = script_pack.get("scripts") or script_pack.get("items")
    if isinstance(scripts, list) and scripts and isinstance(scripts[0], dict):
        first = scripts[0]
        title = title or str(first.get("title") or "")
        hook = hook or str(first.get("hook") or "")
        body = body or str(
            first.get("short_script") or first.get("caption") or ""
        )
    plan = script_pack.get("plan")
    if isinstance(plan, dict):
        title = title or str(plan.get("title") or "")
        hook = hook or str(plan.get("hook") or "")
    return title.strip(), hook.strip(), body.strip()


def _transcript_text(transcript: dict[str, Any] | None) -> str:
    if not isinstance(transcript, dict):
        return ""
    for key in ("cleaned_text", "raw_text", "text"):
        val = transcript.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    sentences = transcript.get("sentences") or []
    if isinstance(sentences, list):
        bits: list[str] = []
        for s in sentences[:40]:
            if isinstance(s, dict):
                t = str(s.get("text") or s.get("sentence") or "").strip()
            else:
                t = str(s).strip()
            if t:
                bits.append(t)
        if bits:
            return " ".join(bits)
    return ""


def _gather_signals(
    *,
    script_pack: dict[str, Any] | None,
    transcript: dict[str, Any] | None,
    speech_transcript: dict[str, Any] | None,
    seo_pack: dict[str, Any] | None,
    trend_pack: dict[str, Any] | None,
    platform_pack: dict[str, Any] | None,
) -> dict[str, Any]:
    title, hook, body = _dig_title_hook(script_pack)
    hashtags: list[str] = []
    trend_topics: list[str] = []

    if isinstance(seo_pack, dict):
        plan = seo_pack.get("plan") or {}
        if isinstance(plan, dict) and not plan.get("skipped"):
            title = title or str(plan.get("title") or "")
            hook = hook or str(plan.get("description") or "")
            hashtags.extend(_as_list(plan.get("hashtags")))
            body = body or str(plan.get("description") or "")

    if isinstance(platform_pack, dict):
        plan = platform_pack.get("plan") or {}
        meta = plan.get("metadata") if isinstance(plan, dict) else {}
        if isinstance(meta, dict):
            title = title or str(meta.get("title") or "")
            hook = hook or str(meta.get("hook") or "")
            hashtags.extend(_as_list(meta.get("hashtags")))

    if isinstance(trend_pack, dict):
        plan = trend_pack.get("plan") or {}
        if isinstance(plan, dict) and not plan.get("skipped"):
            trend_topics.extend(_as_list(plan.get("trend_topics")))
            hashtags.extend(_as_list(plan.get("trending_hashtags")))

    excerpt = body or hook or title
    excerpt = excerpt or _transcript_text(speech_transcript) or _transcript_text(transcript)
    if len(excerpt) > 4000:
        excerpt = excerpt[:3999].rstrip() + "…"

    return {
        "title": title,
        "hook": hook,
        "excerpt": excerpt,
        "hashtags": hashtags[:12],
        "trend_topics": trend_topics[:8],
    }


def _heuristic_batch(
    signals: dict[str, Any],
    hints: dict[str, Any],
) -> GeminiRepurposeBatch:
    title = signals.get("title") or "Key takeaways"
    hook = signals.get("hook") or title
    excerpt = signals.get("excerpt") or hook
    tags = " ".join(signals.get("hashtags") or [])
    sents = _sentences(excerpt) or [hook, title]

    def lim(key: str, default: int = 500) -> int:
        cfg = hints.get(key) or {}
        return int(cfg.get("max_chars") or default)

    short_script = _clamp(f"{hook}\n\n{excerpt}", lim("reels"))
    blog = _clamp(
        f"{title}\n\n{excerpt}\n\nTakeaway: {hook}",
        lim("blog_summary", 1200),
    )
    linkedin = _clamp(
        f"{title}\n\n{hook}\n\n{excerpt}\n\nWhat would you add?",
        lim("linkedin_post", 1300),
    )
    thread_n = int((hints.get("twitter_thread") or {}).get("max_tweets") or 5)
    tweet_lim = int(
        (hints.get("twitter_thread") or {}).get("max_chars_per_tweet") or 260
    )
    thread = [_clamp(f"{i + 1}/ {s}", tweet_lim) for i, s in enumerate(sents[:thread_n])]
    if len(thread) < 2:
        thread = [
            _clamp(f"1/ {title}", tweet_lim),
            _clamp(f"2/ {hook}", tweet_lim),
            _clamp("3/ Full breakdown in the comments.", tweet_lim),
        ]
    ig = _clamp(f"{hook}\n\n{excerpt}\n\n{tags}".strip(), lim("instagram_caption", 800))
    news = _clamp(f"This week: {title}. {excerpt}", lim("newsletter_summary", 900))

    return GeminiRepurposeBatch(
        reels=short_script,
        shorts=_clamp(short_script, lim("shorts")),
        tiktok=_clamp(f"POV: {hook}\n\n{excerpt}", lim("tiktok", 400)),
        blog_summary=blog,
        linkedin_post=linkedin,
        twitter_thread=thread,
        instagram_caption=ig,
        newsletter_summary=news,
    )


def build_repurpose_pack(
    *,
    enabled: bool = True,
    config: VideoJobConfig | None = None,
    source_type: str | SourceType | None = None,
    script_pack: dict[str, Any] | None = None,
    transcript: dict[str, Any] | None = None,
    speech_transcript: dict[str, Any] | None = None,
    seo_pack: dict[str, Any] | None = None,
    trend_pack: dict[str, Any] | None = None,
    platform_pack: dict[str, Any] | None = None,
    brand_pack: dict[str, Any] | None = None,
    analyze_fn: AnalyzeFn | None = None,
) -> RepurposePack:
    job = config or VideoJobConfig()
    explicit = (getattr(job, "repurpose_source", None) or "").strip()
    source_kind = resolve_source_kind(explicit, source_type=source_type)
    platform = (job.platform or "").strip() or "YouTube"
    label = explicit or source_kind

    if not enabled:
        plan = RepurposePlan(
            source_kind=source_kind,
            platform=platform,
            provider="none",
            skipped=True,
            notes="Repurpose feature flag off — skipped.",
        )
        return RepurposePack(
            source_label=label,
            plan=plan,
            fallback=False,
            notes=plan.notes,
        )

    signals = _gather_signals(
        script_pack=script_pack,
        transcript=transcript,
        speech_transcript=speech_transcript,
        seo_pack=seo_pack,
        trend_pack=trend_pack,
        platform_pack=platform_pack,
    )
    hints = format_hints()
    batch: GeminiRepurposeBatch | None = None
    provider = "heuristic"
    fallback = False
    notes_extra = ""

    settings = get_settings()
    use_gemini = bool(analyze_fn is not None or settings.has_gemini_api_key)
    if use_gemini:
        try:
            from tools.llm.gemini import analyze_repurpose

            fn = analyze_fn or analyze_repurpose
            batch = fn(
                source_kind=source_kind,
                platform=platform,
                audience=job.audience or "General",
                source_excerpt=signals["excerpt"],
                title=signals["title"],
                hook=signals["hook"],
                hashtags=signals["hashtags"],
                trend_topics=signals["trend_topics"],
                format_hints=json.dumps(hints, ensure_ascii=False),
            )
            provider = "gemini"
        except Exception as exc:  # noqa: BLE001
            notes_extra = f" Gemini failed ({exc}); heuristic fallback."
            batch = None
            provider = "heuristic"
            fallback = True

    if batch is None:
        batch = _heuristic_batch(signals, hints)
        provider = "heuristic"
        fallback = True

    plan = RepurposePlan(
        source_kind=source_kind,
        reels=(batch.reels or "").strip(),
        shorts=(batch.shorts or "").strip(),
        tiktok=(batch.tiktok or "").strip(),
        blog_summary=(batch.blog_summary or "").strip(),
        linkedin_post=(batch.linkedin_post or "").strip(),
        twitter_thread=[str(t).strip() for t in (batch.twitter_thread or []) if str(t).strip()],
        instagram_caption=(batch.instagram_caption or "").strip(),
        newsletter_summary=(batch.newsletter_summary or "").strip(),
        platform=platform,
        provider=provider,
        skipped=False,
        notes=(
            f"Repurposed {source_kind} into 8 formats via {provider}."
            f"{notes_extra} Plan only (MVP)."
        ),
    )
    from tools.brand.catalog import brand_constraint_notes

    brand_notes = brand_constraint_notes(brand_pack)
    if brand_notes:
        plan = plan.model_copy(
            update={"notes": f"{plan.notes} Brand: {brand_notes}."}
        )
    return RepurposePack(
        source_label=label,
        plan=plan,
        fallback=fallback,
        notes=plan.notes,
    )
