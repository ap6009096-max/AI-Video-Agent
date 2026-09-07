"""Video generation catalog — provider-agnostic plan builder."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

from config.settings import get_settings
from schemas.job import VideoJobConfig
from schemas.video_generation import (
    GeminiVideoGenerationBatch,
    VideoGenerationPack,
    VideoGenerationPlan,
    VideoGenShot,
)

_CATALOG_PATH = (
    Path(__file__).resolve().parent.parent.parent / "config" / "video_generation.json"
)

AnalyzeFn = Callable[..., GeminiVideoGenerationBatch]


@lru_cache(maxsize=1)
def _load_raw() -> dict[str, Any]:
    return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))


def clear_video_generation_cache() -> None:
    _load_raw.cache_clear()


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _norm(value: str) -> str:
    return " ".join((value or "").strip().lower().replace("_", " ").replace("-", " ").split())


def resolve_mode(name: str, catalog: dict[str, Any] | None = None) -> str:
    """Map video_type / label to a supported generation mode."""
    raw = catalog or _load_raw()
    modes = raw.get("modes") or {}
    key = _norm(name)
    if not key:
        return "Cinematic"
    for mode_name, meta in modes.items():
        if _norm(str(mode_name)) == key:
            return str(mode_name)
        for alias in meta.get("aliases") or []:
            if _norm(str(alias)) == key or key in _norm(str(alias)):
                return str(mode_name)
    # Soft contains
    for mode_name in modes:
        if _norm(str(mode_name)) in key or key in _norm(str(mode_name)):
            return str(mode_name)
    return "Cinematic"


def _clamp_duration(value: Any, *, default: float, lo: float, hi: float) -> float:
    try:
        d = float(value)
    except (TypeError, ValueError):
        d = default
    return max(lo, min(hi, round(d, 1)))


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text or "")
    return [p.strip() for p in parts if p and p.strip()]


def _gather_signals(
    script_pack: dict[str, Any] | None,
    storyboard_pack: dict[str, Any] | None,
    visual_style_pack: dict[str, Any] | None,
    environment_pack: dict[str, Any] | None,
    config: VideoJobConfig,
    director_pack: dict[str, Any] | None = None,
) -> dict[str, Any]:
    title = ""
    hook = ""
    script_bits: list[str] = []
    storyboard_rows: list[dict[str, Any]] = []

    style = _safe_str(config.visual_style) or "Cinematic"
    environment = _safe_str(config.environment) or "Wildlife/Nature Forest"
    mode_hint = _safe_str(config.video_type) or "Cinematic"

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

    if isinstance(storyboard_pack, dict):
        plan = storyboard_pack.get("plan") or {}
        shots = plan.get("shots") if isinstance(plan, dict) else None
        if isinstance(shots, list):
            for s in shots:
                if isinstance(s, dict) and not plan.get("skipped"):
                    storyboard_rows.append(s)

    # Prefer Director scene_order when present
    if isinstance(director_pack, dict) and storyboard_rows:
        dplan = director_pack.get("plan") or {}
        if isinstance(dplan, dict) and not dplan.get("skipped"):
            order = dplan.get("scene_order") or []
            if isinstance(order, list) and order:
                by_scene: dict[int, dict[str, Any]] = {}
                for r in storyboard_rows:
                    try:
                        by_scene[int(r.get("scene") or 0)] = r
                    except (TypeError, ValueError):
                        continue
                reordered: list[dict[str, Any]] = []
                seen: set[int] = set()
                for n in order:
                    try:
                        sc = int(n)
                    except (TypeError, ValueError):
                        continue
                    if sc in by_scene and sc not in seen:
                        reordered.append(by_scene[sc])
                        seen.add(sc)
                for r in storyboard_rows:
                    try:
                        sc = int(r.get("scene") or 0)
                    except (TypeError, ValueError):
                        continue
                    if sc not in seen:
                        reordered.append(r)
                        seen.add(sc)
                if reordered:
                    storyboard_rows = reordered

    return {
        "title": title,
        "hook": hook,
        "style": style,
        "environment": environment,
        "mode_hint": mode_hint,
        "script_block": "\n".join(script_bits)[:1600],
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
    mode: str,
) -> GeminiVideoGenerationBatch:
    modes = catalog.get("modes") or {}
    meta = modes.get(mode) or modes.get("Cinematic") or {}
    cameras = list(meta.get("camera_moves") or ["static medium", "gentle push"])
    shot_types = list(catalog.get("shot_types") or ["medium", "close-up", "wide"])
    transitions = list(catalog.get("transitions") or ["cut", "dissolve", "fade"])
    suffix = _safe_str(meta.get("prompt_suffix"))
    default_dur = float(catalog.get("default_duration") or 5.0)
    lo = float(catalog.get("min_duration") or 2.0)
    hi = float(catalog.get("max_duration") or 8.0)
    max_shots = int(catalog.get("max_shots") or 12)

    shots: list[VideoGenShot] = []
    rows = signals.get("storyboard_rows") or []
    if rows:
        for i, row in enumerate(rows[:max_shots], start=1):
            visual = _safe_str(row.get("visual")) or signals["hook"] or "scene beat"
            vo = _safe_str(row.get("voiceover"))
            cam = _safe_str(row.get("camera")) or cameras[(i - 1) % len(cameras)]
            prompt = (
                f"{visual}. Mode: {mode}. Style: {signals['style']}. "
                f"Environment: {signals['environment']}. "
                f"Camera: {cam}."
                + (f" {suffix}." if suffix else "")
            )
            shots.append(
                VideoGenShot(
                    scene=int(row.get("scene") or i),
                    duration=_clamp_duration(
                        row.get("duration"), default=default_dur, lo=lo, hi=hi
                    ),
                    prompt=prompt,
                    visual_style=signals["style"],
                    environment=signals["environment"],
                    camera_move=cam,
                    shot_type=shot_types[(i - 1) % len(shot_types)],
                    transition=_safe_str(row.get("transition")) or transitions[(i - 1) % len(transitions)],
                    voiceover=vo,
                )
            )
        return GeminiVideoGenerationBatch(
            shots=shots, notes="Heuristic video plan from storyboard."
        )

    blob = " ".join(
        filter(None, [signals.get("hook"), signals.get("script_block")])
    )
    sentences = _split_sentences(blob) or [
        signals.get("hook") or signals.get("title") or "Open on environment",
        "Develop the core idea on screen",
        "Close with a clear payoff",
    ]
    for i, line in enumerate(sentences[:max_shots], start=1):
        cam = cameras[(i - 1) % len(cameras)]
        prompt = (
            f"{line}. Mode: {mode}. Style: {signals['style']}. "
            f"Environment: {signals['environment']}. Camera: {cam}."
            + (f" {suffix}." if suffix else "")
        )
        shots.append(
            VideoGenShot(
                scene=i,
                duration=_clamp_duration(default_dur, default=default_dur, lo=lo, hi=hi),
                prompt=prompt,
                visual_style=signals["style"],
                environment=signals["environment"],
                camera_move=cam,
                shot_type=shot_types[(i - 1) % len(shot_types)],
                transition=transitions[(i - 1) % len(transitions)],
                voiceover=line[:240],
            )
        )
    return GeminiVideoGenerationBatch(
        shots=shots, notes="Heuristic video plan from script."
    )


def _normalize_shots(
    raw: list[VideoGenShot],
    catalog: dict[str, Any],
    *,
    style: str,
    environment: str,
) -> list[VideoGenShot]:
    default_dur = float(catalog.get("default_duration") or 5.0)
    lo = float(catalog.get("min_duration") or 2.0)
    hi = float(catalog.get("max_duration") or 8.0)
    max_shots = int(catalog.get("max_shots") or 12)
    out: list[VideoGenShot] = []
    for i, shot in enumerate(list(raw)[:max_shots], start=1):
        out.append(
            VideoGenShot(
                scene=i,
                duration=_clamp_duration(
                    shot.duration, default=default_dur, lo=lo, hi=hi
                ),
                prompt=_safe_str(shot.prompt) or f"Scene {i} visual",
                visual_style=_safe_str(shot.visual_style) or style,
                environment=_safe_str(shot.environment) or environment,
                camera_move=_safe_str(shot.camera_move) or "static medium",
                shot_type=_safe_str(shot.shot_type) or "medium",
                transition=_safe_str(shot.transition) or "cut",
                voiceover=_safe_str(shot.voiceover),
            )
        )
    return out


def _cast_prompt_suffix(character_pack: dict[str, Any] | None) -> str:
    if not isinstance(character_pack, dict):
        return ""
    plan = character_pack.get("plan") or {}
    if not isinstance(plan, dict) or plan.get("skipped"):
        return ""
    bits: list[str] = []
    for c in (plan.get("characters") or [])[:4]:
        if not isinstance(c, dict):
            continue
        name = _safe_str(c.get("name"))
        if not name:
            continue
        bits.append(
            f"{name}: {_safe_str(c.get('appearance'))}; "
            f"clothing={_safe_str(c.get('clothing'))}"
        )
    notes = [
        _safe_str(n) for n in (plan.get("consistency_notes") or [])[:2] if _safe_str(n)
    ]
    parts = []
    if bits:
        parts.append("Cast consistency: " + "; ".join(bits))
    if notes:
        parts.append(" ".join(notes))
    return " ".join(parts)


def _apply_camera_pack(
    shots: list[VideoGenShot],
    camera_pack: dict[str, Any] | None,
) -> list[VideoGenShot]:
    if not isinstance(camera_pack, dict) or not shots:
        return shots
    plan = camera_pack.get("plan") or {}
    if not isinstance(plan, dict) or plan.get("skipped"):
        return shots
    by_scene: dict[int, dict[str, Any]] = {}
    for item in plan.get("instructions") or []:
        if not isinstance(item, dict):
            continue
        try:
            sc = int(item.get("scene") or 0)
        except (TypeError, ValueError):
            continue
        if sc >= 1:
            by_scene[sc] = item
    if not by_scene:
        return shots
    out: list[VideoGenShot] = []
    for s in shots:
        meta = by_scene.get(s.scene)
        if not meta:
            out.append(s)
            continue
        shot_type = _safe_str(meta.get("shot_type")) or s.shot_type
        movement = _safe_str(meta.get("movement")) or s.camera_move
        instruction = _safe_str(meta.get("instruction"))
        prompt = s.prompt
        if instruction and instruction not in prompt:
            prompt = f"{prompt} Camera: {instruction}".strip()
        out.append(
            VideoGenShot(
                **{
                    **s.model_dump(),
                    "shot_type": shot_type,
                    "camera_move": movement,
                    "prompt": prompt,
                }
            )
        )
    return out


def _apply_motion_graphics_pack(
    shots: list[VideoGenShot],
    motion_graphics_pack: dict[str, Any] | None,
) -> list[VideoGenShot]:
    if not isinstance(motion_graphics_pack, dict) or not shots:
        return shots
    plan = motion_graphics_pack.get("plan") or {}
    if not isinstance(plan, dict) or plan.get("skipped"):
        return shots
    by_scene: dict[int, list[str]] = {}
    for item in plan.get("overlays") or []:
        if not isinstance(item, dict):
            continue
        try:
            sc = int(item.get("scene") or 0)
        except (TypeError, ValueError):
            continue
        if sc < 1:
            continue
        kind = _safe_str(item.get("kind")) or "overlay"
        text = _safe_str(item.get("text"))
        cue = f"{kind}: {text}".strip(": ").strip()
        if cue:
            by_scene.setdefault(sc, []).append(cue)
    if not by_scene:
        return shots
    out: list[VideoGenShot] = []
    for s in shots:
        cues = by_scene.get(s.scene) or []
        if not cues:
            out.append(s)
            continue
        suffix = "Motion graphics: " + "; ".join(cues[:3])
        prompt = s.prompt
        if suffix not in prompt:
            prompt = f"{prompt} {suffix}".strip()
        out.append(VideoGenShot(**{**s.model_dump(), "prompt": prompt}))
    return out


def _apply_documentary_pack(
    shots: list[VideoGenShot],
    documentary_pack: dict[str, Any] | None,
) -> list[VideoGenShot]:
    if not isinstance(documentary_pack, dict) or not shots:
        return shots
    plan = documentary_pack.get("plan") or {}
    if not isinstance(plan, dict) or plan.get("skipped"):
        return shots
    intro = _safe_str(plan.get("introduction"))
    conclusion = _safe_str(plan.get("conclusion"))
    by_scene: dict[int, list[str]] = {}
    for item in plan.get("chapters") or []:
        if not isinstance(item, dict):
            continue
        try:
            sc = int(item.get("scene") or 0)
        except (TypeError, ValueError):
            continue
        if sc < 1:
            continue
        title = _safe_str(item.get("title"))
        summary = _safe_str(item.get("summary"))
        cue = f"{title}: {summary}".strip(": ").strip()
        if cue:
            by_scene.setdefault(sc, []).append(cue)
    out: list[VideoGenShot] = []
    for i, s in enumerate(shots):
        parts: list[str] = []
        if i == 0 and intro:
            parts.append(f"Documentary intro: {intro[:120]}")
        cues = by_scene.get(s.scene) or []
        if cues:
            parts.append("Documentary chapter: " + "; ".join(cues[:2]))
        if i == len(shots) - 1 and conclusion:
            parts.append(f"Documentary conclusion: {conclusion[:120]}")
        if not parts:
            out.append(s)
            continue
        suffix = " ".join(parts)
        prompt = s.prompt
        if suffix not in prompt:
            prompt = f"{prompt} {suffix}".strip()
        out.append(VideoGenShot(**{**s.model_dump(), "prompt": prompt}))
    return out


def build_video_generation_pack(
    *,
    enabled: bool = True,
    config: VideoJobConfig | None = None,
    script_pack: dict[str, Any] | None = None,
    storyboard_pack: dict[str, Any] | None = None,
    visual_style_pack: dict[str, Any] | None = None,
    environment_pack: dict[str, Any] | None = None,
    director_pack: dict[str, Any] | None = None,
    character_pack: dict[str, Any] | None = None,
    camera_pack: dict[str, Any] | None = None,
    motion_graphics_pack: dict[str, Any] | None = None,
    documentary_pack: dict[str, Any] | None = None,
    analyze_fn: AnalyzeFn | None = None,
) -> VideoGenerationPack:
    job = config or VideoJobConfig()
    catalog = _load_raw()
    signals = _gather_signals(
        script_pack,
        storyboard_pack,
        visual_style_pack,
        environment_pack,
        job,
        director_pack=director_pack,
    )
    mode = resolve_mode(signals["mode_hint"], catalog)
    style = signals["style"]
    environment = signals["environment"]

    if not enabled:
        plan = VideoGenerationPlan(
            mode=mode,
            style=style,
            environment=environment,
            provider="none",
            skipped=True,
            notes="Video generation feature flag off — skipped.",
        )
        return VideoGenerationPack(source_label=mode, plan=plan, notes=plan.notes)

    batch: GeminiVideoGenerationBatch | None = None
    provider = "heuristic"
    notes_extra = ""
    fallback = False

    settings = get_settings()
    use_gemini = bool(analyze_fn is not None or settings.has_gemini_api_key)
    if use_gemini:
        try:
            from tools.llm.gemini import analyze_video_generation

            fn = analyze_fn or analyze_video_generation
            modes = catalog.get("modes") or {}
            meta = modes.get(mode) or {}
            batch = fn(
                mode=mode,
                style=style,
                environment=environment,
                audience=job.audience or "General",
                title=signals["title"],
                hook=signals["hook"],
                script_block=signals["script_block"],
                storyboard_block=signals["storyboard_block"],
                mode_suffix=_safe_str(meta.get("prompt_suffix")),
                camera_vocab=", ".join(meta.get("camera_moves") or []),
            )
            provider = "gemini"
        except Exception as exc:  # noqa: BLE001
            notes_extra = f" Gemini failed ({exc}); heuristic fallback."
            batch = None
            provider = "heuristic"
            fallback = True

    if batch is None:
        batch = _heuristic_batch(catalog, signals, mode)
        provider = "heuristic"
        fallback = True

    shots = _normalize_shots(
        list(batch.shots or []),
        catalog,
        style=style,
        environment=environment,
    )
    shots = _apply_camera_pack(shots, camera_pack)
    shots = _apply_motion_graphics_pack(shots, motion_graphics_pack)
    shots = _apply_documentary_pack(shots, documentary_pack)
    cast_suffix = _cast_prompt_suffix(character_pack)
    if cast_suffix:
        shots = [
            VideoGenShot(
                **{
                    **s.model_dump(),
                    "prompt": f"{s.prompt} {cast_suffix}".strip(),
                }
            )
            for s in shots
        ]
    shot_sequence = [
        f"scene {s.scene}: {s.shot_type} / {s.camera_move} ({s.duration}s)"
        for s in shots
    ]
    camera_movement_plan = [f"scene {s.scene}: {s.camera_move}" for s in shots]
    scene_prompts = [s.prompt for s in shots]

    plan = VideoGenerationPlan(
        shots=shots,
        shot_sequence=shot_sequence,
        camera_movement_plan=camera_movement_plan,
        scene_prompts=scene_prompts,
        mode=mode,
        style=style,
        environment=environment,
        provider=provider,
        skipped=False,
        notes=(
            f"Provider-agnostic video generation plan via {provider} "
            f"({len(shots)} shots, mode={mode}).{notes_extra} "
            "No vendor SDK calls — plan only."
        ),
    )
    return VideoGenerationPack(
        source_label=mode,
        plan=plan,
        fallback=fallback,
        notes=plan.notes,
    )
