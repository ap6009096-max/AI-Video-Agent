"""Post-process moment candidates: merge, score floor, per-category caps."""

from __future__ import annotations

from config.settings import get_settings
from schemas.moments import DetectedMoment, MomentCategory


def postprocess_moments(
    moments: list[DetectedMoment],
    *,
    min_score: float | None = None,
    max_per_category: int | None = None,
    min_duration: float | None = None,
    merge_gap: float | None = None,
) -> list[DetectedMoment]:
    settings = get_settings()
    min_s = float(min_score if min_score is not None else settings.moment_min_score)
    max_n = int(
        max_per_category
        if max_per_category is not None
        else settings.moment_max_per_category
    )
    min_d = float(
        min_duration if min_duration is not None else settings.moment_min_duration
    )
    gap = float(merge_gap if merge_gap is not None else settings.moment_merge_gap)

    filtered = [m for m in moments if m.score >= min_s]
    # Ensure min duration
    for m in filtered:
        if m.end - m.start < min_d:
            m.end = m.start + min_d

    by_cat: dict[MomentCategory, list[DetectedMoment]] = {}
    for m in filtered:
        by_cat.setdefault(m.category, []).append(m)

    result: list[DetectedMoment] = []
    for category, items in by_cat.items():
        merged = _merge_category(items, gap)
        merged = sorted(merged, key=lambda x: x.score, reverse=True)[:max_n]
        result.extend(merged)

    result.sort(key=lambda m: (m.start, m.category))
    for i, m in enumerate(result):
        m.id = i
        if not m.title:
            m.title = m.transcript[:48] or m.category.replace("_", " ").title()
    return result


def _merge_category(
    items: list[DetectedMoment], gap: float
) -> list[DetectedMoment]:
    if not items:
        return []
    items = sorted(items, key=lambda m: m.start)
    merged: list[DetectedMoment] = [items[0].model_copy(deep=True)]
    for m in items[1:]:
        cur = merged[-1]
        if m.start <= cur.end + gap:
            cur.end = max(cur.end, m.end)
            if m.score > cur.score:
                cur.score = m.score
                cur.reason = m.reason
                cur.title = m.title or cur.title
                cur.transcript = m.transcript or cur.transcript
            # union evidence
            for e in m.evidence:
                if e not in cur.evidence:
                    cur.evidence.append(e)
            if m.transcript and len(m.transcript) > len(cur.transcript):
                cur.transcript = m.transcript
        else:
            merged.append(m.model_copy(deep=True))
    return merged
