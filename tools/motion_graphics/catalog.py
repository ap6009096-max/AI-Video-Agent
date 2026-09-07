"""Motion graphics catalog — graphic-layer overlay plan builder."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

from config.settings import get_settings
from schemas.job import VideoJobConfig
from schemas.motion_graphics import (
    GeminiMotionGraphicsBatch,
    MotionGraphicsPack,
    MotionGraphicsPlan,
    MotionOverlay,
    MotionOverlayKind,
)

_CATALOG_PATH = (
    Path(__file__).resolve().parent.parent.parent / "config" / "motion_graphics.json"
)

_VALID_KINDS: set[str] = {
    "kinetic_typography",
    "animated_title",
    "lower_third",
    "data_visualization",
    "chart",
    "statistic",
    "educational_overlay",
}

AnalyzeFn = Callable[..., GeminiMotionGraphicsBatch]


@lru_cache(maxsize=1)
def _load_raw() -> dict[str, Any]:
    return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))


def clear_motion_graphics_cache() -> None:
    _load_raw.cache_clear()


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _norm_kind(value: str) -> MotionOverlayKind:
    key = _safe_str(value).lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "kinetic": "kinetic_typography",
        "kinetic_type": "kinetic_typography",
        "title": "animated_title",
        "animated_titles": "animated_title",
        "lowerthirds": "lower_third",
        "nameplate": "lower_third",
        "dataviz": "data_visualization",
        "data_viz": "data_visualization",
        "infographic": "data_visualization",
        "stats": "statistic",
        "stat": "statistic",
        "edu": "educational_overlay",
        "tip": "educational_overlay",
    }
    key = aliases.get(key, key)
    if key in _VALID_KINDS:
        return key  # type: ignore[return-value]
    return "educational_overlay"


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text or "")
    return [p.strip() for p in parts if p and p.strip()]


def _find_numbers(text: str) -> list[str]:
    return re.findall(r"\b\d+(?:\.\d+)?%?\b", text or "")


def _gather_signals(
    script_pack: dict[str, Any] | None,
    storyboard_pack: dict[str, Any] | None,
    director_pack: dict[str, Any] | None,
    camera_pack: dict[str, Any] | None,
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
    if isinstance(director_pack, dict):
        plan = director_pack.get("plan") or {}
        if isinstance(plan, dict) and not plan.get("skipped"):
            notes = plan.get("continuity_notes") or []
            flow = plan.get("camera_flow") or []
            director_block = "\n".join(
                [_safe_str(n) for n in list(notes)[:6] + list(flow)[:4] if _safe_str(n)]
            )

    camera_block = ""
    if isinstance(camera_pack, dict):
        plan = camera_pack.get("plan") or {}
        if isinstance(plan, dict) and not plan.get("skipped"):
            summary = plan.get("camera_plan") or []
            camera_block = "\n".join(_safe_str(s) for s in summary[:8] if _safe_str(s))

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
        "camera_block": camera_block[:800],
        "numbers": _find_numbers(script_block + " " + hook),
        "scene_ids": [
            int(r.get("scene") or i)
            for i, r in enumerate(storyboard_rows[:12], start=1)
        ]
        or [1],
    }


def _defaults(kind: str, catalog: dict[str, Any]) -> dict[str, Any]:
    kinds = catalog.get("kinds") or {}
    return dict(kinds.get(kind) or {})


def _heuristic_batch(
    catalog: dict[str, Any],
    signals: dict[str, Any],
) -> GeminiMotionGraphicsBatch:
    max_overlays = int(catalog.get("max_overlays") or 12)
    overlays: list[MotionOverlay] = []
    scenes = list(signals.get("scene_ids") or [1])
    scene1 = scenes[0] if scenes else 1

    title = signals.get("title") or signals.get("hook") or "Untitled"
    d = _defaults("animated_title", catalog)
    overlays.append(
        MotionOverlay(
            scene=scene1,
            kind="animated_title",
            text=title[:80],
            style=_safe_str(d.get("style")),
            animation=_safe_str(d.get("animation")),
            timing=_safe_str(d.get("timing")),
            position=_safe_str(d.get("position")),
        )
    )

    for name in (signals.get("character_names") or [])[:2]:
        if name.lower() == "narrator":
            continue
        d = _defaults("lower_third", catalog)
        overlays.append(
            MotionOverlay(
                scene=scenes[min(1, len(scenes) - 1)],
                kind="lower_third",
                text=name,
                style=_safe_str(d.get("style")),
                animation=_safe_str(d.get("animation")),
                timing=_safe_str(d.get("timing")),
                position=_safe_str(d.get("position")),
            )
        )

    vo_bits = []
    for r in signals.get("storyboard_rows") or []:
        vo = _safe_str(r.get("voiceover"))
        if vo and len(vo.split()) <= 8:
            vo_bits.append((int(r.get("scene") or scene1), vo))
    if not vo_bits and signals.get("hook"):
        vo_bits.append((scene1, _safe_str(signals.get("hook"))[:60]))
    for sc, vo in vo_bits[:2]:
        d = _defaults("kinetic_typography", catalog)
        overlays.append(
            MotionOverlay(
                scene=sc,
                kind="kinetic_typography",
                text=vo[:80],
                style=_safe_str(d.get("style")),
                animation=_safe_str(d.get("animation")),
                timing=_safe_str(d.get("timing")),
                position=_safe_str(d.get("position")),
            )
        )

    numbers = list(signals.get("numbers") or [])
    if numbers:
        d = _defaults("statistic", catalog)
        overlays.append(
            MotionOverlay(
                scene=scenes[min(len(scenes) - 1, 1)],
                kind="statistic",
                text=f"Key figure: {numbers[0]}",
                style=_safe_str(d.get("style")),
                animation=_safe_str(d.get("animation")),
                timing=_safe_str(d.get("timing")),
                position=_safe_str(d.get("position")),
                data=numbers[0],
            )
        )
        if len(numbers) >= 2:
            d = _defaults("chart", catalog)
            overlays.append(
                MotionOverlay(
                    scene=scenes[min(len(scenes) - 1, 2)],
                    kind="chart",
                    text="Comparison snapshot",
                    style=_safe_str(d.get("style")),
                    animation=_safe_str(d.get("animation")),
                    timing=_safe_str(d.get("timing")),
                    position=_safe_str(d.get("position")),
                    data=", ".join(numbers[:4]),
                )
            )
            d = _defaults("data_visualization", catalog)
            overlays.append(
                MotionOverlay(
                    scene=scenes[-1],
                    kind="data_visualization",
                    text="Data highlight panel",
                    style=_safe_str(d.get("style")),
                    animation=_safe_str(d.get("animation")),
                    timing=_safe_str(d.get("timing")),
                    position=_safe_str(d.get("position")),
                    data=", ".join(numbers[:4]),
                )
            )

    vt = (signals.get("video_type") or "").lower()
    educational = any(
        k in vt for k in ("explain", "educat", "how", "tutorial", "lesson")
    )
    if educational or "tip" in (signals.get("script_block") or "").lower():
        d = _defaults("educational_overlay", catalog)
        tip = _split_sentences(signals.get("script_block") or "")
        tip_text = tip[1] if len(tip) > 1 else (tip[0] if tip else "Key takeaway")
        overlays.append(
            MotionOverlay(
                scene=scenes[-1],
                kind="educational_overlay",
                text=tip_text[:90],
                style=_safe_str(d.get("style")),
                animation=_safe_str(d.get("animation")),
                timing=_safe_str(d.get("timing")),
                position=_safe_str(d.get("position")),
            )
        )

    return GeminiMotionGraphicsBatch(
        overlays=overlays[:max_overlays],
        notes="Heuristic motion graphics plan from script/storyboard.",
    )


def _normalize(
    raw: list[MotionOverlay],
    catalog: dict[str, Any],
) -> list[MotionOverlay]:
    max_overlays = int(catalog.get("max_overlays") or 12)
    out: list[MotionOverlay] = []
    for i, item in enumerate(list(raw)[:max_overlays], start=1):
        try:
            scene = int(item.scene or i)
        except (TypeError, ValueError):
            scene = i
        kind = _norm_kind(str(item.kind))
        d = _defaults(kind, catalog)
        out.append(
            MotionOverlay(
                scene=max(1, scene),
                kind=kind,
                text=_safe_str(item.text) or f"{kind.replace('_', ' ').title()}",
                style=_safe_str(item.style) or _safe_str(d.get("style")),
                animation=_safe_str(item.animation) or _safe_str(d.get("animation")),
                timing=_safe_str(item.timing) or _safe_str(d.get("timing")),
                position=_safe_str(item.position) or _safe_str(d.get("position")),
                data=_safe_str(item.data),
                notes=_safe_str(item.notes),
            )
        )
    return out


def build_motion_graphics_pack(
    *,
    enabled: bool = True,
    config: VideoJobConfig | None = None,
    script_pack: dict[str, Any] | None = None,
    storyboard_pack: dict[str, Any] | None = None,
    director_pack: dict[str, Any] | None = None,
    camera_pack: dict[str, Any] | None = None,
    character_pack: dict[str, Any] | None = None,
    visual_style_pack: dict[str, Any] | None = None,
    analyze_fn: AnalyzeFn | None = None,
) -> MotionGraphicsPack:
    job = config or VideoJobConfig()
    catalog = _load_raw()
    signals = _gather_signals(
        script_pack,
        storyboard_pack,
        director_pack,
        camera_pack,
        character_pack,
        visual_style_pack,
        job,
    )
    label = signals["style"] or "Motion Graphics"

    if not enabled:
        plan = MotionGraphicsPlan(
            provider="none",
            skipped=True,
            notes="Motion graphics feature flag off — skipped.",
        )
        return MotionGraphicsPack(source_label=label, plan=plan, notes=plan.notes)

    batch: GeminiMotionGraphicsBatch | None = None
    provider = "heuristic"
    notes_extra = ""
    fallback = False

    settings = get_settings()
    use_gemini = bool(analyze_fn is not None or settings.has_gemini_api_key)
    if use_gemini:
        try:
            from tools.llm.gemini import analyze_motion_graphics

            fn = analyze_fn or analyze_motion_graphics
            kinds = catalog.get("kinds") or {}
            kind_vocab = ", ".join(str(k) for k in kinds.keys())
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
                camera_block=signals["camera_block"],
                character_block=signals["character_block"],
                kind_vocab=kind_vocab,
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

    overlays = _normalize(list(batch.overlays or []), catalog)
    motion_plan = [
        f"scene {o.scene}: {o.kind} - {o.text[:60]}" for o in overlays
    ]

    plan = MotionGraphicsPlan(
        overlays=overlays,
        motion_plan=motion_plan,
        provider=provider,
        skipped=False,
        notes=(
            f"Motion graphics plan via {provider} "
            f"({len(overlays)} overlays).{notes_extra} Plan only."
        ),
    )
    return MotionGraphicsPack(
        source_label=label,
        plan=plan,
        fallback=fallback,
        notes=plan.notes,
    )
