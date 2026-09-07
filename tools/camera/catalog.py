"""Camera catalog — per-scene camera instruction builder."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

from config.settings import get_settings
from schemas.camera import (
    CameraInstruction,
    CameraPack,
    CameraPlan,
    CameraShotType,
    GeminiCameraBatch,
)
from schemas.job import VideoJobConfig

_CATALOG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "camera.json"

_VALID: set[str] = {
    "wide",
    "medium",
    "close_up",
    "extreme_close_up",
    "drone",
    "tracking",
    "pov",
    "cinematic",
}

AnalyzeFn = Callable[..., GeminiCameraBatch]


@lru_cache(maxsize=1)
def _load_raw() -> dict[str, Any]:
    return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))


def clear_camera_cache() -> None:
    _load_raw.cache_clear()


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _norm(value: str) -> str:
    return " ".join(
        (value or "").strip().lower().replace("_", " ").replace("-", " ").split()
    )


def resolve_shot_type(
    hint: str, catalog: dict[str, Any] | None = None
) -> CameraShotType:
    raw = catalog or _load_raw()
    types = raw.get("shot_types") or {}
    key = _norm(hint)
    if not key:
        return "medium"
    compact = key.replace(" ", "_")
    if compact in _VALID:
        return compact  # type: ignore[return-value]
    for name, meta in types.items():
        if _norm(str(name)) == key:
            return str(name)  # type: ignore[return-value]
        for alias in meta.get("aliases") or []:
            if _norm(str(alias)) == key or key in _norm(str(alias)):
                return str(name)  # type: ignore[return-value]
    # Soft keyword contains
    for token, name in (
        ("extreme close", "extreme_close_up"),
        ("close up", "close_up"),
        ("closeup", "close_up"),
        ("drone", "drone"),
        ("aerial", "drone"),
        ("track", "tracking"),
        ("dolly", "tracking"),
        ("pov", "pov"),
        ("cinematic", "cinematic"),
        ("wide", "wide"),
        ("establish", "wide"),
        ("medium", "medium"),
    ):
        if token in key:
            return name  # type: ignore[return-value]
    return "medium"


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text or "")
    return [p.strip() for p in parts if p and p.strip()]


def _gather_signals(
    script_pack: dict[str, Any] | None,
    storyboard_pack: dict[str, Any] | None,
    character_pack: dict[str, Any] | None,
    visual_style_pack: dict[str, Any] | None,
    environment_pack: dict[str, Any] | None,
    config: VideoJobConfig,
) -> dict[str, Any]:
    title = ""
    hook = ""
    script_bits: list[str] = []
    storyboard_rows: list[dict[str, Any]] = []
    character_bits: list[str] = []

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
                    character_bits.append(
                        f"{c.get('name')} ({c.get('role_type')}): "
                        f"{c.get('appearance')}; clothing={c.get('clothing')}"
                    )

    return {
        "title": title,
        "hook": hook,
        "style": style,
        "environment": environment,
        "script_block": "\n".join(script_bits)[:1600],
        "storyboard_rows": storyboard_rows,
        "storyboard_block": "\n".join(
            f"scene {r.get('scene')}: cam={r.get('camera')}; "
            f"visual={r.get('visual')}; vo={r.get('voiceover')}"
            for r in storyboard_rows[:12]
        )[:1600],
        "character_block": "\n".join(character_bits)[:800],
    }


def _meta_for(shot_type: str, catalog: dict[str, Any]) -> dict[str, Any]:
    types = catalog.get("shot_types") or {}
    return dict(types.get(shot_type) or types.get("medium") or {})


def _heuristic_batch(
    catalog: dict[str, Any],
    signals: dict[str, Any],
) -> GeminiCameraBatch:
    max_scenes = int(catalog.get("max_scenes") or 12)
    order = list((catalog.get("shot_types") or {}).keys()) or [
        "wide",
        "medium",
        "close_up",
        "cinematic",
    ]
    rows = list(signals.get("storyboard_rows") or [])
    instructions: list[CameraInstruction] = []

    if rows:
        for i, row in enumerate(rows[:max_scenes], start=1):
            try:
                scene = int(row.get("scene") or i)
            except (TypeError, ValueError):
                scene = i
            hint = _safe_str(row.get("camera"))
            shot_type = resolve_shot_type(hint, catalog)
            meta = _meta_for(shot_type, catalog)
            movement = _safe_str(meta.get("default_movement")) or "subtle move"
            visual = _safe_str(row.get("visual"))
            base = _safe_str(meta.get("instruction")) or f"{shot_type} on subject"
            instruction = (
                f"Scene {scene}: {base} Style={signals['style']}. "
                f"Environment={signals['environment']}."
                + (f" Subject cue: {visual}." if visual else "")
            )
            instructions.append(
                CameraInstruction(
                    scene=scene,
                    shot_type=shot_type,  # type: ignore[arg-type]
                    movement=movement,
                    instruction=instruction,
                    lens="35mm" if shot_type in {"wide", "drone"} else "50mm",
                )
            )
    else:
        blob = " ".join(
            filter(None, [signals.get("hook"), signals.get("script_block")])
        )
        sentences = _split_sentences(blob) or [
            signals.get("hook") or signals.get("title") or "Open",
            "Develop",
            "Close",
        ]
        for i, line in enumerate(sentences[:max_scenes], start=1):
            shot_type = str(order[(i - 1) % len(order)])
            meta = _meta_for(shot_type, catalog)
            movement = _safe_str(meta.get("default_movement")) or "subtle move"
            base = _safe_str(meta.get("instruction")) or f"{shot_type} framing"
            instructions.append(
                CameraInstruction(
                    scene=i,
                    shot_type=shot_type,  # type: ignore[arg-type]
                    movement=movement,
                    instruction=f"Scene {i}: {base} Beat: {line[:120]}",
                    lens="50mm",
                )
            )

    return GeminiCameraBatch(
        instructions=instructions,
        notes="Heuristic camera plan from storyboard/script.",
    )


def _normalize(
    raw: list[CameraInstruction],
    catalog: dict[str, Any],
) -> list[CameraInstruction]:
    max_scenes = int(catalog.get("max_scenes") or 12)
    out: list[CameraInstruction] = []
    for i, item in enumerate(list(raw)[:max_scenes], start=1):
        try:
            scene = int(item.scene or i)
        except (TypeError, ValueError):
            scene = i
        shot_type = resolve_shot_type(str(item.shot_type), catalog)
        meta = _meta_for(shot_type, catalog)
        movement = _safe_str(item.movement) or _safe_str(
            meta.get("default_movement")
        )
        instruction = _safe_str(item.instruction) or _safe_str(
            meta.get("instruction")
        )
        out.append(
            CameraInstruction(
                scene=scene,
                shot_type=shot_type,  # type: ignore[arg-type]
                movement=movement,
                instruction=instruction or f"Scene {scene}: {shot_type} framing",
                lens=_safe_str(item.lens),
                notes=_safe_str(item.notes),
            )
        )
    return out


def build_camera_pack(
    *,
    enabled: bool = True,
    config: VideoJobConfig | None = None,
    script_pack: dict[str, Any] | None = None,
    storyboard_pack: dict[str, Any] | None = None,
    character_pack: dict[str, Any] | None = None,
    visual_style_pack: dict[str, Any] | None = None,
    environment_pack: dict[str, Any] | None = None,
    analyze_fn: AnalyzeFn | None = None,
) -> CameraPack:
    job = config or VideoJobConfig()
    catalog = _load_raw()
    signals = _gather_signals(
        script_pack,
        storyboard_pack,
        character_pack,
        visual_style_pack,
        environment_pack,
        job,
    )
    label = signals["style"] or "Camera"

    if not enabled:
        plan = CameraPlan(
            provider="none",
            skipped=True,
            notes="Camera feature flag off — skipped.",
        )
        return CameraPack(source_label=label, plan=plan, notes=plan.notes)

    batch: GeminiCameraBatch | None = None
    provider = "heuristic"
    notes_extra = ""
    fallback = False

    settings = get_settings()
    use_gemini = bool(analyze_fn is not None or settings.has_gemini_api_key)
    if use_gemini:
        try:
            from tools.llm.gemini import analyze_camera

            fn = analyze_fn or analyze_camera
            types = catalog.get("shot_types") or {}
            shot_vocab = ", ".join(str(k) for k in types.keys())
            batch = fn(
                style=signals["style"],
                environment=signals["environment"],
                audience=job.audience or "General",
                title=signals["title"],
                hook=signals["hook"],
                script_block=signals["script_block"],
                storyboard_block=signals["storyboard_block"],
                character_block=signals["character_block"],
                shot_vocab=shot_vocab,
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

    instructions = _normalize(list(batch.instructions or []), catalog)
    camera_plan = [
        f"scene {i.scene}: {i.shot_type} / {i.movement}" for i in instructions
    ]

    plan = CameraPlan(
        instructions=instructions,
        camera_plan=camera_plan,
        provider=provider,
        skipped=False,
        notes=(
            f"Camera plan via {provider} "
            f"({len(instructions)} scenes).{notes_extra} Plan only."
        ),
    )
    return CameraPack(
        source_label=label,
        plan=plan,
        fallback=fallback,
        notes=plan.notes,
    )
