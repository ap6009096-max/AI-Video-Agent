"""Storyboard catalog and pack builder (Gemini + heuristic fallback)."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

from config.settings import get_settings
from schemas.job import VideoJobConfig
from schemas.storyboard import (
    GeminiStoryboardBatch,
    StoryboardPack,
    StoryboardPlan,
    StoryboardShot,
)

_CATALOG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "storyboards.json"

AnalyzeFn = Callable[..., GeminiStoryboardBatch]


@lru_cache(maxsize=1)
def _load_raw() -> dict[str, Any]:
    return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))


def clear_storyboard_cache() -> None:
    _load_raw.cache_clear()


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


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
    transcript: dict[str, Any] | None,
    scenes: dict[str, Any] | None,
    stories: dict[str, Any] | None,
    visual_style_pack: dict[str, Any] | None,
    environment_pack: dict[str, Any] | None,
    config: VideoJobConfig,
) -> dict[str, Any]:
    title = ""
    hook = ""
    script_bits: list[str] = []
    scene_bits: list[str] = []
    story_bits: list[str] = []
    transcript_excerpt = ""

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
                primary.get("script") or primary.get("short_script") or primary.get("caption")
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
        items = stories.get("stories") or stories.get("items") or []
        if isinstance(items, list):
            for i, st in enumerate(items[:4], start=1):
                if not isinstance(st, dict):
                    continue
                hook = hook or _safe_str(st.get("hook"))
                story_bits.append(
                    f"beat_{i}: "
                    + " / ".join(
                        filter(
                            None,
                            [
                                _safe_str(st.get("hook")),
                                _safe_str(st.get("context")),
                                _safe_str(st.get("value") or st.get("event")),
                                _safe_str(st.get("payoff")),
                                _safe_str(st.get("cta")),
                            ],
                        )
                    )[:280]
                )

    if isinstance(scenes, dict):
        items = scenes.get("scenes") or scenes.get("items") or []
        if isinstance(items, list):
            for i, sc in enumerate(items[:6], start=1):
                if not isinstance(sc, dict):
                    continue
                label = _safe_str(
                    sc.get("description")
                    or sc.get("label")
                    or sc.get("summary")
                    or f"scene {i}"
                )
                dur = sc.get("duration") or sc.get("duration_seconds")
                scene_bits.append(f"scene_{i}: {label[:200]} (dur={dur})")

    if isinstance(transcript, dict):
        text = _safe_str(
            transcript.get("cleaned_text")
            or transcript.get("text")
            or transcript.get("full_text")
        )
        transcript_excerpt = text[:800]

    return {
        "title": title,
        "hook": hook,
        "style": style,
        "environment": environment,
        "script_block": "\n".join(script_bits)[:1600],
        "scene_block": "\n".join(scene_bits)[:1200],
        "story_block": "\n".join(story_bits)[:1200],
        "transcript_excerpt": transcript_excerpt,
    }


def _heuristic_batch(
    catalog: dict[str, Any],
    signals: dict[str, Any],
) -> GeminiStoryboardBatch:
    cameras = list(catalog.get("cameras") or ["wide establishing", "medium shot", "close-up"])
    transitions = list(catalog.get("transitions") or ["cut", "dissolve", "fade"])
    default_dur = float(catalog.get("default_duration") or 5.0)
    lo = float(catalog.get("min_duration") or 2.0)
    hi = float(catalog.get("max_duration") or 8.0)
    max_shots = int(catalog.get("max_shots") or 12)

    blob = " ".join(
        filter(
            None,
            [
                signals.get("hook"),
                signals.get("script_block"),
                signals.get("transcript_excerpt"),
                signals.get("story_block"),
            ],
        )
    )
    sentences = _split_sentences(blob)
    if not sentences:
        sentences = [
            signals.get("hook") or signals.get("title") or "Open on environment",
            "Develop the core idea on screen",
            "Close with a clear payoff or CTA",
        ]

    shots: list[StoryboardShot] = []
    for i, line in enumerate(sentences[:max_shots], start=1):
        cam = cameras[(i - 1) % len(cameras)]
        trans = transitions[(i - 1) % len(transitions)] if i < len(sentences[:max_shots]) else "fade"
        visual = (
            f"{signals['environment']} — {line[:120]}. "
            f"Style: {signals['style']}."
        )
        shots.append(
            StoryboardShot(
                scene=i,
                duration=_clamp_duration(default_dur, default=default_dur, lo=lo, hi=hi),
                camera=cam,
                visual=visual,
                voiceover=line[:240],
                transition=trans,
            )
        )
    return GeminiStoryboardBatch(shots=shots, notes="Heuristic storyboard from script/VO.")


def _normalize_shots(
    raw_shots: list[StoryboardShot],
    catalog: dict[str, Any],
) -> list[StoryboardShot]:
    default_dur = float(catalog.get("default_duration") or 5.0)
    lo = float(catalog.get("min_duration") or 2.0)
    hi = float(catalog.get("max_duration") or 8.0)
    max_shots = int(catalog.get("max_shots") or 12)
    out: list[StoryboardShot] = []
    for i, shot in enumerate(list(raw_shots)[:max_shots], start=1):
        out.append(
            StoryboardShot(
                scene=int(shot.scene) if shot.scene and int(shot.scene) > 0 else i,
                duration=_clamp_duration(
                    shot.duration, default=default_dur, lo=lo, hi=hi
                ),
                camera=_safe_str(shot.camera) or "medium shot",
                visual=_safe_str(shot.visual) or "On-screen visual beat",
                voiceover=_safe_str(shot.voiceover),
                transition=_safe_str(shot.transition) or "cut",
            )
        )
    # Re-number scenes sequentially for stability
    for i, shot in enumerate(out, start=1):
        shot.scene = i
    return out


def build_storyboard_pack(
    *,
    enabled: bool = True,
    config: VideoJobConfig | None = None,
    script_pack: dict[str, Any] | None = None,
    transcript: dict[str, Any] | None = None,
    scenes: dict[str, Any] | None = None,
    stories: dict[str, Any] | None = None,
    visual_style_pack: dict[str, Any] | None = None,
    environment_pack: dict[str, Any] | None = None,
    analyze_fn: AnalyzeFn | None = None,
) -> StoryboardPack:
    job = config or VideoJobConfig()
    catalog = _load_raw()
    signals = _gather_signals(
        script_pack,
        transcript,
        scenes,
        stories,
        visual_style_pack,
        environment_pack,
        job,
    )
    label = signals["style"]

    if not enabled:
        plan = StoryboardPlan(
            provider="none",
            skipped=True,
            notes="Storyboard feature flag off — skipped.",
        )
        return StoryboardPack(source_label=label, plan=plan, notes=plan.notes)

    batch: GeminiStoryboardBatch | None = None
    provider = "heuristic"
    notes_extra = ""
    fallback = False

    settings = get_settings()
    use_gemini = bool(analyze_fn is not None or settings.has_gemini_api_key)
    if use_gemini:
        try:
            from tools.llm.gemini import analyze_storyboard

            fn = analyze_fn or analyze_storyboard
            batch = fn(
                style=signals["style"],
                environment=signals["environment"],
                audience=job.audience or "General",
                title=signals["title"],
                hook=signals["hook"],
                script_block=signals["script_block"],
                transcript_excerpt=signals["transcript_excerpt"],
                scene_block=signals["scene_block"],
                story_block=signals["story_block"],
                camera_vocab=", ".join(catalog.get("cameras") or []),
                transition_vocab=", ".join(catalog.get("transitions") or []),
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

    shots = _normalize_shots(list(batch.shots or []), catalog)
    camera_plan = [f"scene {s.scene}: {s.camera}" for s in shots]
    transition_plan = [f"scene {s.scene} → {s.transition}" for s in shots]

    plan = StoryboardPlan(
        shots=shots,
        shot_list=list(shots),
        scene_list=list(shots),
        camera_plan=camera_plan,
        transition_plan=transition_plan,
        provider=provider,
        skipped=False,
        notes=(
            f"Storyboard planned via {provider} ({len(shots)} shots)."
            f"{notes_extra} Plan only (before render)."
        ),
    )
    return StoryboardPack(
        source_label=label,
        plan=plan,
        fallback=fallback,
        notes=plan.notes,
    )
