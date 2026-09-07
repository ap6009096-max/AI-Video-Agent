"""Content calendar pack builder — daily / weekly / monthly schedules."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from typing import Any

from config.settings import get_settings
from schemas.calendar import (
    CalendarEntry,
    CalendarPack,
    CalendarPlan,
    DailyPlan,
    GeminiCalendarBatch,
    MonthlySchedule,
    WeeklySchedule,
)
from schemas.job import VideoJobConfig

EnrichFn = Callable[..., GeminiCalendarBatch]


def _norm(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def _dedupe(items: list[str], *, limit: int = 64) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = (item or "").strip()
        if not text:
            continue
        key = _norm(text)
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _parse_anchor(anchor_date: str | date | datetime | None) -> date:
    if isinstance(anchor_date, datetime):
        return anchor_date.date()
    if isinstance(anchor_date, date):
        return anchor_date
    if isinstance(anchor_date, str) and anchor_date.strip():
        raw = anchor_date.strip()[:10]
        try:
            return date.fromisoformat(raw)
        except ValueError:
            pass
    return datetime.now(timezone.utc).date()


def _dig_platform(
    config: VideoJobConfig,
    platform_pack: dict[str, Any] | None,
) -> str:
    if isinstance(platform_pack, dict):
        plan = platform_pack.get("plan") or {}
        if isinstance(plan, dict):
            name = str(plan.get("platform") or plan.get("name") or "").strip()
            if name:
                return name
        meta = platform_pack.get("source_label") or platform_pack.get("platform")
        if meta:
            return str(meta).strip()
    return (config.platform or "").strip() or "YouTube"


def _dig_video_type(
    config: VideoJobConfig,
    video_type_pack: dict[str, Any] | None,
) -> str:
    if isinstance(video_type_pack, dict):
        plan = video_type_pack.get("plan") or {}
        if isinstance(plan, dict):
            name = str(plan.get("name") or plan.get("video_type") or "").strip()
            if name:
                return name
        label = video_type_pack.get("source_label") or video_type_pack.get("video_type")
        if label:
            return str(label).strip()
    return (config.video_type or "").strip() or "Shorts"


def _collect_topic_seeds(
    *,
    script_pack: dict[str, Any] | None,
    research_report: dict[str, Any] | None,
    trend_pack: dict[str, Any] | None,
    repurpose_pack: dict[str, Any] | None,
    config: VideoJobConfig,
) -> list[str]:
    seeds: list[str] = []

    if isinstance(script_pack, dict):
        primary = script_pack.get("primary") or script_pack.get("script")
        if isinstance(primary, dict):
            for key in ("title", "hook", "topic"):
                val = str(primary.get(key) or "").strip()
                if val:
                    seeds.append(val)
        scripts = script_pack.get("scripts") or script_pack.get("items")
        if isinstance(scripts, list):
            for item in scripts:
                if not isinstance(item, dict):
                    continue
                for key in ("title", "hook", "topic"):
                    val = str(item.get(key) or "").strip()
                    if val:
                        seeds.append(val)

    if isinstance(research_report, dict):
        topic = str(research_report.get("topic") or "").strip()
        if topic:
            seeds.append(topic)
        outline = research_report.get("outline") or research_report.get("sections")
        if isinstance(outline, list):
            for row in outline:
                if isinstance(row, dict):
                    heading = str(
                        row.get("heading") or row.get("title") or row.get("topic") or ""
                    ).strip()
                    if heading:
                        seeds.append(heading)
                elif isinstance(row, str) and row.strip():
                    seeds.append(row.strip())
        claims = research_report.get("claims")
        if isinstance(claims, list):
            for claim in claims[:8]:
                if isinstance(claim, dict):
                    text = str(claim.get("claim") or claim.get("text") or "").strip()
                    if text:
                        seeds.append(text[:120])

    if isinstance(trend_pack, dict):
        plan = trend_pack.get("plan") or {}
        if isinstance(plan, dict):
            for key in ("trend_topics", "topic_labels", "trending_keywords"):
                raw = plan.get(key) or []
                if isinstance(raw, list):
                    seeds.extend(str(x).strip() for x in raw if str(x).strip())

    if isinstance(repurpose_pack, dict):
        plan = repurpose_pack.get("plan") or {}
        if isinstance(plan, dict):
            for key in (
                "reels",
                "shorts",
                "tiktok",
                "blog_summary",
                "linkedin_post",
                "instagram_caption",
                "newsletter_summary",
            ):
                val = str(plan.get(key) or "").strip()
                if val:
                    # Use format label + short excerpt as a seed
                    seeds.append(f"{key.replace('_', ' ').title()}: {val[:80]}")
            thread = plan.get("twitter_thread")
            if isinstance(thread, list) and thread:
                seeds.append(f"Thread: {str(thread[0])[:80]}")

    if config.audience:
        seeds.append(f"{config.audience} tips")
    if not seeds:
        seeds.append(f"{config.video_type or 'Shorts'} content idea")
        seeds.append(f"{config.platform or 'YouTube'} weekly post")

    return _dedupe(seeds, limit=48)


def _monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _group_views(entries: list[CalendarEntry]) -> tuple[
    list[DailyPlan], list[WeeklySchedule], list[MonthlySchedule]
]:
    by_day: dict[str, list[CalendarEntry]] = {}
    by_week: dict[str, list[CalendarEntry]] = {}
    by_month: dict[str, list[CalendarEntry]] = {}

    for entry in entries:
        d = entry.date
        by_day.setdefault(d, []).append(entry)
        try:
            parsed = date.fromisoformat(d)
        except ValueError:
            continue
        week_start = _monday_of(parsed)
        week_key = week_start.isoformat()
        by_week.setdefault(week_key, []).append(entry)
        month_key = f"{parsed.year:04d}-{parsed.month:02d}"
        by_month.setdefault(month_key, []).append(entry)

    daily = [
        DailyPlan(date=day, entries=list(items))
        for day, items in sorted(by_day.items())
    ]
    weekly: list[WeeklySchedule] = []
    for week_start_s, items in sorted(by_week.items()):
        start = date.fromisoformat(week_start_s)
        end = start + timedelta(days=6)
        weekly.append(
            WeeklySchedule(
                week_start=start.isoformat(),
                week_end=end.isoformat(),
                entries=list(items),
            )
        )
    monthly = [
        MonthlySchedule(month=month, entries=list(items))
        for month, items in sorted(by_month.items())
    ]
    return daily, weekly, monthly


def _schedule_dates(
    anchor: date,
    *,
    horizon_days: int,
    posts_per_week: int,
) -> list[date]:
    """Even fill Mon–Sun across the horizon at ~posts_per_week cadence."""
    horizon = max(1, int(horizon_days))
    ppw = max(1, min(7, int(posts_per_week)))
    # Target total posts ≈ horizon * ppw / 7
    target = max(1, int(round(horizon * ppw / 7.0)))
    if target >= horizon:
        return [anchor + timedelta(days=i) for i in range(horizon)]

    dates: list[date] = []
    # Spread evenly across all days including weekends
    for i in range(target):
        offset = int(round(i * (horizon - 1) / max(1, target - 1))) if target > 1 else 0
        offset = min(horizon - 1, max(0, offset))
        d = anchor + timedelta(days=offset)
        if not dates or dates[-1] != d:
            dates.append(d)
        else:
            # nudge forward if collision
            nxt = min(anchor + timedelta(days=horizon - 1), d + timedelta(days=1))
            if nxt != dates[-1]:
                dates.append(nxt)
    return dates


def build_calendar_pack(
    *,
    enabled: bool = True,
    config: VideoJobConfig | None = None,
    script_pack: dict[str, Any] | None = None,
    research_report: dict[str, Any] | None = None,
    trend_pack: dict[str, Any] | None = None,
    repurpose_pack: dict[str, Any] | None = None,
    video_type_pack: dict[str, Any] | None = None,
    platform_pack: dict[str, Any] | None = None,
    brand_pack: dict[str, Any] | None = None,
    anchor_date: str | date | datetime | None = None,
    horizon_days: int | None = None,
    posts_per_week: int | None = None,
    enrich_fn: EnrichFn | None = None,
) -> CalendarPack:
    job = config or VideoJobConfig()
    settings = get_settings()
    horizon = int(
        horizon_days
        if horizon_days is not None
        else getattr(settings, "calendar_horizon_days", 30)
    )
    ppw = int(
        posts_per_week
        if posts_per_week is not None
        else getattr(settings, "calendar_posts_per_week", 7)
    )
    horizon = max(1, horizon)
    ppw = max(1, min(7, ppw))
    anchor = _parse_anchor(anchor_date)
    platform = _dig_platform(job, platform_pack)
    video_type = _dig_video_type(job, video_type_pack)

    if not enabled:
        plan = CalendarPlan(
            horizon_days=horizon,
            anchor_date=anchor.isoformat(),
            platform=platform,
            video_type=video_type,
            provider="none",
            skipped=True,
            notes="Content calendar feature flag off — skipped.",
        )
        return CalendarPack(
            source_label=platform,
            plan=plan,
            fallback=False,
            notes=plan.notes,
        )

    seeds = _collect_topic_seeds(
        script_pack=script_pack,
        research_report=research_report,
        trend_pack=trend_pack,
        repurpose_pack=repurpose_pack,
        config=job,
    )
    schedule = _schedule_dates(anchor, horizon_days=horizon, posts_per_week=ppw)

    topics = list(seeds)
    provider = "heuristic"
    fallback = True
    notes_extra = ""

    use_gemini = bool(enrich_fn is not None or settings.has_gemini_api_key)
    if use_gemini:
        try:
            from tools.llm.gemini import enrich_calendar_topics

            fn = enrich_fn or enrich_calendar_topics
            batch = fn(
                platform=platform,
                video_type=video_type,
                audience=job.audience or "General",
                seed_topics=seeds,
                dates=[d.isoformat() for d in schedule],
            )
            enriched = [
                str(t).strip() for t in (batch.topics or []) if str(t).strip()
            ]
            if enriched:
                # Align length to schedule; cycle if short
                topics = []
                for i in range(len(schedule)):
                    topics.append(enriched[i % len(enriched)])
                provider = "gemini"
                fallback = False
                if batch.notes:
                    notes_extra = f" {batch.notes}"
        except Exception as exc:  # noqa: BLE001
            notes_extra = f" Gemini failed ({exc}); heuristic fallback."
            provider = "heuristic"
            fallback = True

    entries: list[CalendarEntry] = []
    for i, day in enumerate(schedule):
        topic = topics[i % len(topics)] if topics else f"Day {i + 1} idea"
        # Light variation for heuristic cycling
        if provider == "heuristic" and i >= len(seeds) and seeds:
            topic = f"{seeds[i % len(seeds)]} ({day.strftime('%a')})"
        entries.append(
            CalendarEntry(
                date=day.isoformat(),
                topic=topic,
                platform=platform,
                video_type=video_type,
            )
        )

    daily, weekly, monthly = _group_views(entries)
    plan = CalendarPlan(
        entries=entries,
        daily=daily,
        weekly=weekly,
        monthly=monthly,
        horizon_days=horizon,
        anchor_date=anchor.isoformat(),
        platform=platform,
        video_type=video_type,
        provider=provider,
        skipped=False,
        notes=(
            f"Calendar for {platform}/{video_type}: {len(entries)} slots "
            f"over {horizon}d via {provider}.{notes_extra} Plan only (MVP)."
        ),
    )
    from tools.brand.catalog import brand_constraint_notes

    brand_notes = brand_constraint_notes(brand_pack)
    if brand_notes:
        plan = plan.model_copy(
            update={"notes": f"{plan.notes} Brand: {brand_notes}."}
        )
    return CalendarPack(
        source_label=platform,
        plan=plan,
        fallback=fallback,
        notes=plan.notes,
    )
