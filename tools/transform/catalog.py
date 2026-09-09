"""Build TransformIntent packs from NL + scene context (Gemini optional)."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from schemas.job import VideoJobConfig
from schemas.transform_intent import (
    GeminiTransformBatch,
    TransformIntent,
    TransformIntentPack,
    TransformIntentPlan,
)

AnalyzeFn = Callable[..., GeminiTransformBatch]

_DEFAULT_PRESERVED = [
    "host",
    "background",
    "music",
    "camera",
    "other_scenes",
]

_DEFAULT_SCOPE = ["dialogue", "voice"]


def _safe(value: Any) -> str:
    return str(value or "").strip()


def _scene_count(scenes: dict[str, Any] | None) -> int:
    if not isinstance(scenes, dict):
        return 0
    items = scenes.get("scenes") or scenes.get("cuts") or []
    if isinstance(items, list) and items:
        return len(items)
    return 0


def _parse_scene_index(raw: str | int | None, instruction: str) -> int | str:
    if isinstance(raw, int) and raw > 0:
        return raw
    text = _safe(raw)
    if text.isdigit():
        return int(text)
    m = re.search(r"scene\s*[#:]?\s*(\d+)", instruction, flags=re.I)
    if m:
        return int(m.group(1))
    m2 = re.search(r"scene[_\s-]?(\d+)", text, flags=re.I)
    if m2:
        return int(m2.group(1))
    return text or 1


def _heuristic_changes(instruction: str) -> tuple[list[str], list[str], list[str]]:
    low = instruction.lower()
    changes: list[str] = []
    scope: list[str] = []
    unsupported: list[str] = []

    if any(k in low for k in ("shorten", "shorter", "trim", "cut down", "concise")):
        changes.append("shorten dialogue")
        scope.extend(["dialogue", "trim", "voice"])
    if any(k in low for k in ("funnier", "funny", "humor", "joke", "wittier")):
        changes.append("make dialogue funnier")
        scope.extend(["dialogue", "voice"])
    if any(k in low for k in ("rewrite", "rephrase", "change dialogue", "say ")):
        changes.append("rewrite dialogue")
        scope.extend(["dialogue", "voice"])
    if any(k in low for k in ("caption", "subtitle")):
        changes.append("update captions")
        scope.append("captions")
    if any(k in low for k in ("voice", "tts", "narrat", "accent")):
        changes.append("regenerate voice")
        scope.append("voice")
    if any(k in low for k in ("reframe", "vertical", "9:16", "crop")):
        changes.append("reframe scene")
        scope.append("reframe")
    if any(
        k in low
        for k in (
            "replace face",
            "change appearance",
            "generate new video",
            "deepfake",
            "animate guest",
            "new b-roll face",
        )
    ):
        unsupported.append("generative video / face synthesis (not supported in Phase 1)")

    if not changes and instruction.strip():
        changes.append(instruction.strip()[:120])
        scope.extend(list(_DEFAULT_SCOPE))

    # Dedupe preserve order
    def _uniq(items: list[str]) -> list[str]:
        out: list[str] = []
        for i in items:
            if i and i not in out:
                out.append(i)
        return out

    return _uniq(changes), _uniq(scope), _uniq(unsupported)


def _preserved_for(scope: list[str], instruction: str) -> list[str]:
    low = instruction.lower()
    preserved = list(_DEFAULT_PRESERVED)
    if "voice" not in scope and "voice" not in preserved:
        preserved.append("voice")
    if "captions" not in scope:
        preserved.append("captions")
    if "host" in low and "keep the host" not in low and "preserve host" not in low:
        pass
    if "guest" in low and any(k in low for k in ("guest", "speaker")):
        if "host" not in preserved:
            preserved.append("host")
    # Always keep other scenes unless instruction says rewrite all
    if "all scenes" not in low and "other_scenes" not in preserved:
        preserved.append("other_scenes")
    out: list[str] = []
    for p in preserved:
        if p not in out:
            out.append(p)
    return out


def parse_transform_heuristic(
    *,
    instruction: str,
    target_scene: int | str | None = None,
    target_speaker: str = "",
    scenes: dict[str, Any] | None = None,
    speakers: dict[str, Any] | None = None,
) -> TransformIntent:
    """Rule-based intent when Gemini is unavailable or quota-exhausted."""
    changes, scope, unsupported = _heuristic_changes(instruction)
    scene_id = _parse_scene_index(target_scene, instruction)
    speaker = _safe(target_speaker)
    if not speaker and isinstance(speakers, dict):
        labels = speakers.get("speakers") or speakers.get("labels") or []
        if isinstance(labels, list) and labels:
            first = labels[0]
            if isinstance(first, dict):
                speaker = _safe(first.get("label") or first.get("name") or "speaker")
            else:
                speaker = _safe(first) or "speaker"
    if not speaker:
        low = instruction.lower()
        if "guest" in low:
            speaker = "guest"
        elif "host" in low:
            speaker = "host"
        else:
            speaker = "speaker"

    total = _scene_count(scenes)
    return TransformIntent(
        target_scene=scene_id,
        target_speaker=speaker,
        instruction=instruction.strip(),
        requested_changes=changes,
        preserved_elements=_preserved_for(scope, instruction),
        regeneration_scope=scope or list(_DEFAULT_SCOPE),
        unsupported_changes=unsupported,
        scenes_total=total,
        scenes_changed=1 if instruction.strip() else 0,
        notes="Heuristic transform intent (no Gemini).",
    )


def build_transform_intent_pack(
    *,
    enabled: bool,
    instruction: str = "",
    target_scene: int | str | None = None,
    target_speaker: str = "",
    config: VideoJobConfig | None = None,
    scenes: dict[str, Any] | None = None,
    speakers: dict[str, Any] | None = None,
    transcript: dict[str, Any] | None = None,
    analyze_fn: AnalyzeFn | None = None,
) -> TransformIntentPack:
    """Build pack; soft-skip when disabled or no instruction."""
    _ = config
    _ = transcript
    instr = (instruction or "").strip()
    if not enabled or not instr:
        return TransformIntentPack(
            source_label="none",
            plan=TransformIntentPlan(
                skipped=True,
                notes=(
                    "Transform intent skipped "
                    f"(enabled={enabled}, instruction={'yes' if instr else 'no'})."
                ),
            ),
            notes="skipped",
        )

    batch: GeminiTransformBatch | None = None
    provider = "heuristic"
    fallback = True
    if analyze_fn is not None:
        try:
            batch = analyze_fn(
                instruction=instr,
                target_scene=target_scene,
                target_speaker=target_speaker,
                scenes=scenes,
                speakers=speakers,
                transcript=transcript,
            )
            provider = "gemini"
            fallback = False
        except Exception:  # noqa: BLE001
            batch = None
            provider = "heuristic"
            fallback = True

    if batch is not None:
        changes = list(batch.requested_changes) or _heuristic_changes(instr)[0]
        scope = list(batch.regeneration_scope) or _heuristic_changes(instr)[1]
        unsupported = list(batch.unsupported_changes)
        # Generative video always unsupported in Phase 1
        if any(s == "video" for s in scope):
            unsupported.append("generative video pixels (Phase 1 uses FFmpeg reuse)")
            scope = [s for s in scope if s != "video"]
        intent = TransformIntent(
            target_scene=_parse_scene_index(
                batch.target_scene or target_scene, instr
            ),
            target_speaker=_safe(batch.target_speaker) or _safe(target_speaker) or "speaker",
            instruction=instr,
            requested_changes=changes,
            preserved_elements=list(batch.preserved_elements)
            or _preserved_for(scope, instr),
            regeneration_scope=scope,
            unsupported_changes=unsupported,
            scenes_total=_scene_count(scenes),
            scenes_changed=1,
            notes=batch.notes or "Gemini transform intent",
        )
    else:
        intent = parse_transform_heuristic(
            instruction=instr,
            target_scene=target_scene,
            target_speaker=target_speaker,
            scenes=scenes,
            speakers=speakers,
        )

    return TransformIntentPack(
        source_label=instr[:80],
        plan=TransformIntentPlan(
            intent=intent,
            provider=provider,
            skipped=False,
            notes=intent.notes,
        ),
        fallback=fallback,
        notes=f"provider={provider}",
    )
