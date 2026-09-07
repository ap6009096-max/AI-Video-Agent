"""Documentary catalog — narrative arc plan builder."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

from config.settings import get_settings
from schemas.documentary import (
    DocumentaryChapter,
    DocumentaryPack,
    DocumentaryPlan,
    GeminiDocumentaryBatch,
)
from schemas.job import VideoJobConfig

_CATALOG_PATH = (
    Path(__file__).resolve().parent.parent.parent / "config" / "documentary.json"
)

AnalyzeFn = Callable[..., GeminiDocumentaryBatch]


@lru_cache(maxsize=1)
def _load_raw() -> dict[str, Any]:
    return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))


def clear_documentary_cache() -> None:
    _load_raw.cache_clear()


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text or "")
    return [p.strip() for p in parts if p and p.strip()]


def _find_numbers(text: str) -> list[str]:
    return re.findall(r"\b\d+(?:\.\d+)?%?\b", text or "")


def _gather_signals(
    script_pack: dict[str, Any] | None,
    storyboard_pack: dict[str, Any] | None,
    director_pack: dict[str, Any] | None,
    character_pack: dict[str, Any] | None,
    visual_style_pack: dict[str, Any] | None,
    config: VideoJobConfig,
) -> dict[str, Any]:
    title = ""
    hook = ""
    script_bits: list[str] = []
    storyboard_rows: list[dict[str, Any]] = []
    character_names: list[str] = []

    style = _safe_str(config.visual_style) or "Cinematic"
    environment = _safe_str(config.environment) or "Wildlife/Nature Forest"
    video_type = _safe_str(getattr(config, "video_type", "") or "")

    if isinstance(visual_style_pack, dict):
        plan = visual_style_pack.get("plan") or visual_style_pack
        if isinstance(plan, dict):
            style = _safe_str(plan.get("name") or plan.get("style") or style)
        style = _safe_str(visual_style_pack.get("name") or style)

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

    if isinstance(storyboard_pack, dict):
        plan = storyboard_pack.get("plan") or {}
        shots = plan.get("shots") if isinstance(plan, dict) else None
        if isinstance(shots, list) and not plan.get("skipped"):
            for s in shots:
                if isinstance(s, dict):
                    storyboard_rows.append(s)

    if isinstance(character_pack, dict):
        plan = character_pack.get("plan") or {}
        if isinstance(plan, dict) and not plan.get("skipped"):
            for c in plan.get("characters") or []:
                if isinstance(c, dict) and _safe_str(c.get("name")):
                    character_names.append(_safe_str(c.get("name")))

    director_block = ""
    scene_order: list[int] = []
    if isinstance(director_pack, dict):
        plan = director_pack.get("plan") or {}
        if isinstance(plan, dict) and not plan.get("skipped"):
            notes = plan.get("continuity_notes") or []
            flow = plan.get("camera_flow") or []
            director_block = "\n".join(
                [_safe_str(n) for n in list(notes)[:6] + list(flow)[:4] if _safe_str(n)]
            )
            for sc in plan.get("scene_order") or []:
                try:
                    scene_order.append(int(sc))
                except (TypeError, ValueError):
                    continue

    script_block = "\n".join(script_bits)[:1600]
    return {
        "title": title,
        "hook": hook,
        "style": style,
        "environment": environment,
        "video_type": video_type,
        "script_block": script_block,
        "storyboard_rows": storyboard_rows,
        "storyboard_block": "\n".join(
            f"scene {r.get('scene')}: visual={r.get('visual')}; "
            f"vo={r.get('voiceover')}"
            for r in storyboard_rows[:12]
        )[:1600],
        "character_names": character_names,
        "character_block": ", ".join(character_names),
        "director_block": director_block[:800],
        "scene_order": scene_order,
        "numbers": _find_numbers(script_block + " " + hook),
        "sentences": _split_sentences(script_block),
    }


def _heuristic_batch(
    catalog: dict[str, Any],
    signals: dict[str, Any],
) -> GeminiDocumentaryBatch:
    max_chapters = int(catalog.get("max_chapters") or 6)
    defaults = catalog.get("defaults") or {}
    intro_tpl = _safe_str(catalog.get("intro_template")) or "Open: {hook}"
    hook = signals.get("hook") or signals.get("title") or "the central question"
    introduction = intro_tpl.format(hook=hook) if "{hook}" in intro_tpl else intro_tpl
    if signals.get("title") and signals["title"] not in introduction:
        introduction = f"{signals['title']}: {introduction}"

    rows = list(signals.get("storyboard_rows") or [])
    sentences = list(signals.get("sentences") or [])
    chapters: list[DocumentaryChapter] = []

    if rows:
        chunk = max(1, len(rows) // min(4, len(rows)))
        groups: list[list[dict[str, Any]]] = []
        for i in range(0, len(rows), chunk):
            groups.append(rows[i : i + chunk])
            if len(groups) >= max_chapters:
                break
        for gi, group in enumerate(groups, start=1):
            first = group[0]
            scene = int(first.get("scene") or gi)
            vo = _safe_str(first.get("voiceover")) or _safe_str(first.get("visual"))
            title = f"Chapter {gi}: {vo[:40]}" if vo else f"Chapter {gi}"
            summary = "; ".join(
                _safe_str(g.get("visual") or g.get("voiceover")) for g in group[:3]
            )[:160]
            chapters.append(
                DocumentaryChapter(
                    title=title,
                    summary=summary or f"Beat {gi}",
                    research=_safe_str(defaults.get("research")),
                    evidence=_safe_str(defaults.get("evidence")),
                    narration=vo[:120] or _safe_str(defaults.get("narration")),
                    interview="",
                    timeline=f"Scene {scene}",
                    scene=scene,
                )
            )
    else:
        bits = sentences[: max_chapters] or [
            signals.get("hook") or signals.get("title") or "Opening beat"
        ]
        for i, bit in enumerate(bits[:max_chapters], start=1):
            chapters.append(
                DocumentaryChapter(
                    title=f"Chapter {i}",
                    summary=bit[:160],
                    research=_safe_str(defaults.get("research")),
                    evidence=_safe_str(defaults.get("evidence")),
                    narration=bit[:120],
                    interview="",
                    timeline=f"Beat {i}",
                    scene=i,
                )
            )

    speakers = [
        n
        for n in (signals.get("character_names") or [])
        if n.lower() != "narrator"
    ]
    for i, ch in enumerate(chapters):
        if speakers and not ch.interview:
            ch.interview = (
                f"Interview beat with {speakers[i % len(speakers)]}: "
                f"what changed and why it matters."
            )

    numbers = list(signals.get("numbers") or [])
    research_structure = [
        f"Frame the question around: {signals.get('title') or 'the topic'}",
        "List primary sources and open questions per chapter.",
    ]
    evidence_structure = [
        f"Highlight key figure: {numbers[0]}" if numbers else "Use observational B-roll as evidence.",
        "Pair each claim with a concrete visual or quote.",
    ]
    narration_plan = [
        ch.narration for ch in chapters if ch.narration
    ] or [_safe_str(defaults.get("narration"))]
    interview_plan = [
        ch.interview for ch in chapters if ch.interview
    ] or (["No named interviewees — use expert VO only."] if not speakers else [])
    order = list(signals.get("scene_order") or [c.scene for c in chapters])
    timeline_plan = [
        f"Beat {i}: scene {sc}" for i, sc in enumerate(order[:8], start=1)
    ] or [ch.timeline for ch in chapters if ch.timeline]

    conclusion = _safe_str(catalog.get("conclusion_template"))
    if sentences:
        conclusion = f"{conclusion} Final beat: {sentences[-1][:100]}"
    elif chapters:
        conclusion = f"{conclusion} Final chapter: {chapters[-1].title}"

    return GeminiDocumentaryBatch(
        introduction=introduction[:300],
        chapters=chapters[:max_chapters],
        conclusion=conclusion[:300],
        research_structure=research_structure,
        evidence_structure=evidence_structure,
        narration_plan=narration_plan[:8],
        interview_plan=interview_plan[:8],
        timeline_plan=timeline_plan[:8],
        notes="Heuristic documentary plan from script/storyboard.",
    )


def _normalize_chapters(
    raw: list[DocumentaryChapter],
    catalog: dict[str, Any],
) -> list[DocumentaryChapter]:
    max_chapters = int(catalog.get("max_chapters") or 6)
    defaults = catalog.get("defaults") or {}
    out: list[DocumentaryChapter] = []
    for i, item in enumerate(list(raw)[:max_chapters], start=1):
        try:
            scene = int(item.scene or i)
        except (TypeError, ValueError):
            scene = i
        out.append(
            DocumentaryChapter(
                title=_safe_str(item.title) or f"Chapter {i}",
                summary=_safe_str(item.summary) or f"Chapter {i} beat",
                research=_safe_str(item.research) or _safe_str(defaults.get("research")),
                evidence=_safe_str(item.evidence) or _safe_str(defaults.get("evidence")),
                narration=_safe_str(item.narration)
                or _safe_str(defaults.get("narration")),
                interview=_safe_str(item.interview),
                timeline=_safe_str(item.timeline) or f"Beat {i}",
                scene=max(1, scene),
            )
        )
    return out


def build_documentary_pack(
    *,
    enabled: bool = True,
    config: VideoJobConfig | None = None,
    script_pack: dict[str, Any] | None = None,
    storyboard_pack: dict[str, Any] | None = None,
    director_pack: dict[str, Any] | None = None,
    character_pack: dict[str, Any] | None = None,
    visual_style_pack: dict[str, Any] | None = None,
    analyze_fn: AnalyzeFn | None = None,
) -> DocumentaryPack:
    job = config or VideoJobConfig()
    catalog = _load_raw()
    signals = _gather_signals(
        script_pack,
        storyboard_pack,
        director_pack,
        character_pack,
        visual_style_pack,
        job,
    )
    label = signals["style"] or "Documentary"

    if not enabled:
        plan = DocumentaryPlan(
            provider="none",
            skipped=True,
            notes="Documentary feature flag off — skipped.",
        )
        return DocumentaryPack(source_label=label, plan=plan, notes=plan.notes)

    batch: GeminiDocumentaryBatch | None = None
    provider = "heuristic"
    notes_extra = ""
    fallback = False

    settings = get_settings()
    use_gemini = bool(analyze_fn is not None or settings.has_gemini_api_key)
    if use_gemini:
        try:
            from tools.llm.gemini import analyze_documentary

            fn = analyze_fn or analyze_documentary
            defaults = catalog.get("defaults") or {}
            templates_block = "\n".join(
                f"{k}: {v}" for k, v in defaults.items()
            )
            batch = fn(
                style=signals["style"],
                environment=signals["environment"],
                audience=job.audience or "General",
                video_type=signals["video_type"],
                title=signals["title"],
                hook=signals["hook"],
                script_block=signals["script_block"],
                storyboard_block=signals["storyboard_block"],
                director_block=signals["director_block"],
                character_block=signals["character_block"],
                templates_block=templates_block,
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

    chapters = _normalize_chapters(list(batch.chapters or []), catalog)
    introduction = _safe_str(batch.introduction) or (
        signals.get("hook") or signals.get("title") or "Introduction"
    )
    conclusion = _safe_str(batch.conclusion) or "Conclusion"

    def _lines(values: list[Any]) -> list[str]:
        return [_safe_str(v) for v in values if _safe_str(v)][:12]

    research_structure = _lines(list(batch.research_structure or []))
    evidence_structure = _lines(list(batch.evidence_structure or []))
    narration_plan = _lines(list(batch.narration_plan or []))
    interview_plan = _lines(list(batch.interview_plan or []))
    timeline_plan = _lines(list(batch.timeline_plan or []))

    if not research_structure:
        research_structure = [c.research for c in chapters if c.research][:6]
    if not evidence_structure:
        evidence_structure = [c.evidence for c in chapters if c.evidence][:6]
    if not narration_plan:
        narration_plan = [c.narration for c in chapters if c.narration][:6]
    if not interview_plan:
        interview_plan = [c.interview for c in chapters if c.interview][:6]
    if not timeline_plan:
        timeline_plan = [c.timeline for c in chapters if c.timeline][:6]

    documentary_plan = [
        f"intro: {introduction[:80]}",
        *[f"chapter {i}: {c.title}" for i, c in enumerate(chapters, start=1)],
        f"conclusion: {conclusion[:80]}",
    ]

    plan = DocumentaryPlan(
        introduction=introduction[:400],
        chapters=chapters,
        conclusion=conclusion[:400],
        research_structure=research_structure,
        evidence_structure=evidence_structure,
        narration_plan=narration_plan,
        interview_plan=interview_plan,
        timeline_plan=timeline_plan,
        documentary_plan=documentary_plan,
        provider=provider,
        skipped=False,
        notes=(
            f"Documentary plan via {provider} "
            f"({len(chapters)} chapters).{notes_extra} Plan only."
        ),
    )
    return DocumentaryPack(
        source_label=label,
        plan=plan,
        fallback=fallback,
        notes=plan.notes,
    )
