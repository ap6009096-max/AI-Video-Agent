"""Director catalog — scene sequencing and continuity plan builder."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

from config.settings import get_settings
from schemas.director import (
    DirectorBeat,
    DirectorContinuityNote,
    DirectorPack,
    DirectorPlan,
    GeminiDirectorBatch,
)
from schemas.job import VideoJobConfig

_CATALOG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "director.json"

AnalyzeFn = Callable[..., GeminiDirectorBatch]


@lru_cache(maxsize=1)
def _load_raw() -> dict[str, Any]:
    return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))


def clear_director_cache() -> None:
    _load_raw.cache_clear()


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text or "")
    return [p.strip() for p in parts if p and p.strip()]


def _gather_signals(
    script_pack: dict[str, Any] | None,
    storyboard_pack: dict[str, Any] | None,
    stories: dict[str, Any] | None,
    visual_style_pack: dict[str, Any] | None,
    environment_pack: dict[str, Any] | None,
    config: VideoJobConfig,
) -> dict[str, Any]:
    title = ""
    hook = ""
    script_bits: list[str] = []
    story_bits: list[str] = []
    storyboard_rows: list[dict[str, Any]] = []

    style = _safe_str(config.visual_style) or "Cinematic"
    environment = _safe_str(config.environment) or "Wildlife/Nature Forest"

    if isinstance(visual_style_pack, dict):
        plan = visual_style_pack.get("plan") or visual_style_pack
        if isinstance(plan, dict):
            style = _safe_str(plan.get("name") or plan.get("style") or style)
        style = _safe_str(visual_style_pack.get("name") or style)

    if isinstance(environment_pack, dict):
        plan = environment_pack.get("plan") or environment_pack
        if isinstance(plan, dict):
            environment = _safe_str(
                plan.get("name") or plan.get("environment") or environment
            )
        environment = _safe_str(environment_pack.get("name") or environment)

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

    if isinstance(stories, dict):
        items = stories.get("stories") or stories.get("items") or stories.get("beats")
        if isinstance(items, list):
            for item in items[:8]:
                if isinstance(item, dict):
                    beat = _safe_str(
                        item.get("summary")
                        or item.get("beat")
                        or item.get("title")
                        or item.get("text")
                    )
                    if beat:
                        story_bits.append(beat)
                elif item:
                    story_bits.append(_safe_str(item))

    if isinstance(storyboard_pack, dict):
        plan = storyboard_pack.get("plan") or {}
        shots = plan.get("shots") if isinstance(plan, dict) else None
        if isinstance(shots, list) and not plan.get("skipped"):
            for s in shots:
                if isinstance(s, dict):
                    storyboard_rows.append(s)

    return {
        "title": title,
        "hook": hook,
        "style": style,
        "environment": environment,
        "script_block": "\n".join(script_bits)[:1600],
        "story_block": "\n".join(story_bits)[:1200],
        "storyboard_rows": storyboard_rows,
        "storyboard_block": "\n".join(
            f"scene {r.get('scene')}: cam={r.get('camera')}; "
            f"visual={r.get('visual')}; vo={r.get('voiceover')}; "
            f"dur={r.get('duration')}; trans={r.get('transition')}"
            for r in storyboard_rows[:12]
        )[:1600],
    }


def _heuristic_batch(
    catalog: dict[str, Any],
    signals: dict[str, Any],
) -> GeminiDirectorBatch:
    max_scenes = int(catalog.get("max_scenes") or 12)
    prefixes = catalog.get("note_prefixes") or {}
    templates = catalog.get("continuity_templates") or {}
    flow_vocab = list(catalog.get("camera_flow_vocab") or [])

    rows = list(signals.get("storyboard_rows") or [])
    if rows:
        order: list[int] = []
        for i, row in enumerate(rows[:max_scenes], start=1):
            try:
                order.append(int(row.get("scene") or i))
            except (TypeError, ValueError):
                order.append(i)
    else:
        blob = " ".join(
            filter(
                None,
                [
                    signals.get("hook"),
                    signals.get("script_block"),
                    signals.get("story_block"),
                ],
            )
        )
        sentences = _split_sentences(blob) or [
            signals.get("hook") or signals.get("title") or "Open",
            "Develop",
            "Close",
        ]
        order = list(range(1, min(len(sentences), max_scenes) + 1))
        rows = [
            {
                "scene": i,
                "camera": "medium",
                "visual": sentences[i - 1] if i - 1 < len(sentences) else f"Beat {i}",
                "voiceover": sentences[i - 1] if i - 1 < len(sentences) else "",
                "transition": "cut",
            }
            for i in order
        ]

    continuity_notes: list[str] = []
    camera_flow: list[str] = []
    by_scene = {int(r.get("scene") or i): r for i, r in enumerate(rows, start=1)}

    for idx in range(len(order) - 1):
        a, b = order[idx], order[idx + 1]
        ra = by_scene.get(a) or {}
        rb = by_scene.get(b) or {}
        cam_a = _safe_str(ra.get("camera")) or "medium"
        cam_b = _safe_str(rb.get("camera")) or "medium"
        trans = _safe_str(rb.get("transition") or ra.get("transition")) or "cut"

        for kind in ("story", "character", "environment", "camera", "transition"):
            tmpl = _safe_str(templates.get(kind))
            prefix = _safe_str(prefixes.get(kind)) or f"{kind.title()}:"
            if tmpl:
                note = tmpl.format(
                    a=a, b=b, cam_a=cam_a, cam_b=cam_b, transition=trans
                )
            else:
                note = f"Bridge scene {a} to scene {b} ({kind})."
            continuity_notes.append(f"{prefix} {note}")

        if flow_vocab:
            flow = flow_vocab[idx % len(flow_vocab)]
        else:
            flow = f"from {cam_a} into {cam_b}"
        camera_flow.append(f"scene {a}→{b}: {flow} ({cam_a} → {cam_b})")

    if order and not camera_flow:
        first = by_scene.get(order[0]) or {}
        camera_flow.append(
            f"scene {order[0]}: establish with {_safe_str(first.get('camera')) or 'wide'}"
        )

    return GeminiDirectorBatch(
        scene_order=order,
        continuity_notes=continuity_notes[: max_scenes * 5],
        camera_flow=camera_flow[:max_scenes],
        notes="Heuristic director plan from storyboard/script.",
    )


def _normalize_batch(
    batch: GeminiDirectorBatch,
    catalog: dict[str, Any],
    signals: dict[str, Any],
) -> tuple[list[int], list[str], list[str], list[DirectorBeat], list[DirectorContinuityNote]]:
    max_scenes = int(catalog.get("max_scenes") or 12)
    rows = list(signals.get("storyboard_rows") or [])
    fallback_order = [
        int(r.get("scene") or i) for i, r in enumerate(rows[:max_scenes], start=1)
    ] or list(range(1, min(3, max_scenes) + 1))

    raw_order = list(batch.scene_order or [])
    scene_order: list[int] = []
    seen: set[int] = set()
    for n in raw_order:
        try:
            v = int(n)
        except (TypeError, ValueError):
            continue
        if v < 1 or v in seen:
            continue
        seen.add(v)
        scene_order.append(v)
        if len(scene_order) >= max_scenes:
            break
    if not scene_order:
        scene_order = fallback_order

    continuity_notes = [
        _safe_str(n) for n in (batch.continuity_notes or []) if _safe_str(n)
    ][: max_scenes * 5]
    camera_flow = [_safe_str(n) for n in (batch.camera_flow or []) if _safe_str(n)][
        :max_scenes
    ]

    by_scene = {
        int(r.get("scene") or i): r for i, r in enumerate(rows, start=1) if isinstance(r, dict)
    }
    beats: list[DirectorBeat] = []
    for sc in scene_order:
        row = by_scene.get(sc) or {}
        beats.append(
            DirectorBeat(
                scene=sc,
                summary=_safe_str(row.get("visual") or row.get("voiceover"))
                or f"Scene {sc}",
                camera=_safe_str(row.get("camera")),
                environment=signals["environment"],
            )
        )

    structured: list[DirectorContinuityNote] = []
    for idx in range(len(scene_order) - 1):
        a, b = scene_order[idx], scene_order[idx + 1]
        for kind in ("story", "character", "environment", "camera", "transition"):
            matching = next(
                (n for n in continuity_notes if n.lower().startswith(f"{kind}:")),
                "",
            )
            if matching:
                structured.append(
                    DirectorContinuityNote(
                        kind=kind,  # type: ignore[arg-type]
                        from_scene=a,
                        to_scene=b,
                        note=matching,
                    )
                )

    return scene_order, continuity_notes, camera_flow, beats, structured


def _cast_lines(character_pack: dict[str, Any] | None) -> list[str]:
    if not isinstance(character_pack, dict):
        return []
    plan = character_pack.get("plan") or {}
    if not isinstance(plan, dict) or plan.get("skipped"):
        return []
    lines: list[str] = []
    for c in plan.get("characters") or []:
        if not isinstance(c, dict):
            continue
        name = _safe_str(c.get("name"))
        if not name:
            continue
        appearance = _safe_str(c.get("appearance"))
        clothing = _safe_str(c.get("clothing"))
        lines.append(
            f"{name} ({c.get('role_type') or 'human'}): "
            f"{appearance}; clothing={clothing}"
        )
    return lines


def _enrich_with_characters(
    continuity_notes: list[str],
    character_pack: dict[str, Any] | None,
) -> list[str]:
    cast = _cast_lines(character_pack)
    if not cast:
        return continuity_notes
    extra = [
        f"Character: Maintain {line}" for line in cast[:4]
    ]
    # Prefer named cast notes; keep existing notes
    return list(continuity_notes) + extra


def _camera_flow_from_pack(camera_pack: dict[str, Any] | None) -> list[str]:
    if not isinstance(camera_pack, dict):
        return []
    plan = camera_pack.get("plan") or {}
    if not isinstance(plan, dict) or plan.get("skipped"):
        return []
    summary = plan.get("camera_plan")
    if isinstance(summary, list) and summary:
        return [_safe_str(s) for s in summary if _safe_str(s)]
    out: list[str] = []
    for item in plan.get("instructions") or []:
        if not isinstance(item, dict):
            continue
        scene = item.get("scene")
        shot = _safe_str(item.get("shot_type"))
        move = _safe_str(item.get("movement"))
        if scene is None:
            continue
        out.append(f"scene {scene}: {shot} / {move}".strip(" /"))
    return out


def _enrich_camera_flow(
    camera_flow: list[str],
    camera_pack: dict[str, Any] | None,
) -> list[str]:
    seeded = _camera_flow_from_pack(camera_pack)
    if not seeded:
        return camera_flow
    # Prefer dedicated camera plan; keep any extra director flow lines
    existing = [c for c in camera_flow if c not in seeded]
    return list(seeded) + existing


def build_director_pack(
    *,
    enabled: bool = True,
    config: VideoJobConfig | None = None,
    script_pack: dict[str, Any] | None = None,
    storyboard_pack: dict[str, Any] | None = None,
    stories: dict[str, Any] | None = None,
    visual_style_pack: dict[str, Any] | None = None,
    environment_pack: dict[str, Any] | None = None,
    character_pack: dict[str, Any] | None = None,
    camera_pack: dict[str, Any] | None = None,
    analyze_fn: AnalyzeFn | None = None,
) -> DirectorPack:
    job = config or VideoJobConfig()
    catalog = _load_raw()
    signals = _gather_signals(
        script_pack,
        storyboard_pack,
        stories,
        visual_style_pack,
        environment_pack,
        job,
    )
    label = signals["style"] or "Director"

    if not enabled:
        plan = DirectorPlan(
            provider="none",
            skipped=True,
            notes="Director feature flag off — skipped.",
        )
        return DirectorPack(source_label=label, plan=plan, notes=plan.notes)

    batch: GeminiDirectorBatch | None = None
    provider = "heuristic"
    notes_extra = ""
    fallback = False

    settings = get_settings()
    use_gemini = bool(analyze_fn is not None or settings.has_gemini_api_key)
    if use_gemini:
        try:
            from tools.llm.gemini import analyze_director

            fn = analyze_fn or analyze_director
            batch = fn(
                style=signals["style"],
                environment=signals["environment"],
                audience=job.audience or "General",
                title=signals["title"],
                hook=signals["hook"],
                script_block=signals["script_block"],
                storyboard_block=signals["storyboard_block"],
                story_block=signals["story_block"],
                camera_vocab=", ".join(catalog.get("camera_flow_vocab") or []),
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

    scene_order, continuity_notes, camera_flow, beats, structured = _normalize_batch(
        batch, catalog, signals
    )
    continuity_notes = _enrich_with_characters(continuity_notes, character_pack)
    camera_flow = _enrich_camera_flow(camera_flow, camera_pack)

    plan = DirectorPlan(
        scene_order=scene_order,
        continuity_notes=continuity_notes,
        camera_flow=camera_flow,
        beats=beats,
        structured_notes=structured,
        provider=provider,
        skipped=False,
        notes=(
            f"Director continuity plan via {provider} "
            f"({len(scene_order)} scenes).{notes_extra} Plan only."
        ),
    )
    return DirectorPack(
        source_label=label,
        plan=plan,
        fallback=fallback,
        notes=plan.notes,
    )
