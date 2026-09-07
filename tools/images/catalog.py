"""Image generation catalog and pack builder (Gemini + heuristic + file write)."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

from config.settings import get_settings
from schemas.image import (
    GeminiImageBatch,
    GeminiImageItem,
    ImageAssetItem,
    ImageKind,
    ImagePack,
    ImagePlan,
)
from schemas.job import VideoJobConfig
from tools.images.generate import generate_image_file

_CATALOG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "images.json"

AnalyzeFn = Callable[..., GeminiImageBatch]
GenerateFn = Callable[..., tuple[Path, str]]

_VALID_KINDS: set[str] = {
    "scene",
    "storyboard",
    "broll",
    "thumbnail",
    "background",
}


@lru_cache(maxsize=1)
def _load_raw() -> dict[str, Any]:
    return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))


def clear_image_cache() -> None:
    _load_raw.cache_clear()


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _slug(value: str, *, fallback: str = "item") -> str:
    raw = re.sub(r"[^a-zA-Z0-9_-]+", "_", (value or "").strip().lower()).strip("_")
    return (raw[:48] or fallback)


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
            body = _safe_str(primary.get("script") or primary.get("short_script"))
            if body:
                script_bits.append(body[:400])
        scripts = script_pack.get("scripts") or script_pack.get("items")
        if isinstance(scripts, list):
            for s in scripts[:3]:
                if not isinstance(s, dict):
                    continue
                title = title or _safe_str(s.get("title"))
                hook = hook or _safe_str(s.get("hook"))
                body = _safe_str(s.get("script") or s.get("short_script") or s.get("caption"))
                if body:
                    script_bits.append(body[:300])
        # ScriptsReport dump shape
        report = script_pack.get("scripts") if not scripts else None
        if isinstance(script_pack.get("items"), list):
            pass

    if isinstance(stories, dict):
        items = stories.get("stories") or stories.get("items") or []
        if isinstance(items, list):
            for i, st in enumerate(items[:3], start=1):
                if not isinstance(st, dict):
                    continue
                hook = hook or _safe_str(st.get("hook"))
                scene_bits.append(
                    f"story_{i}: "
                    + " / ".join(
                        filter(
                            None,
                            [
                                _safe_str(st.get("hook")),
                                _safe_str(st.get("context")),
                                _safe_str(st.get("payoff")),
                            ],
                        )
                    )[:240]
                )

    if isinstance(scenes, dict):
        items = scenes.get("scenes") or scenes.get("items") or []
        if isinstance(items, list):
            for i, sc in enumerate(items[:4], start=1):
                if not isinstance(sc, dict):
                    continue
                label = _safe_str(
                    sc.get("description")
                    or sc.get("label")
                    or sc.get("summary")
                    or f"scene {i}"
                )
                scene_bits.append(f"scene_{i}: {label[:200]}")

    if isinstance(transcript, dict):
        text = _safe_str(
            transcript.get("cleaned_text")
            or transcript.get("text")
            or transcript.get("full_text")
        )
        transcript_excerpt = text[:500]

    return {
        "title": title,
        "hook": hook,
        "style": style,
        "environment": environment,
        "script_block": "\n".join(script_bits)[:1200],
        "scene_block": "\n".join(scene_bits)[:1200],
        "transcript_excerpt": transcript_excerpt,
    }


def _heuristic_batch(
    catalog: dict[str, Any],
    signals: dict[str, Any],
) -> GeminiImageBatch:
    kinds = list(catalog.get("default_kinds") or ["scene", "storyboard", "broll", "thumbnail", "background"])
    prefixes = catalog.get("kind_prefixes") or {}
    style_sfx = (catalog.get("style_suffixes") or {}).get(signals["style"], "")
    env_sfx = (catalog.get("environment_suffixes") or {}).get(signals["environment"], "")
    subject = signals["hook"] or signals["title"] or signals["scene_block"] or "short form video moment"
    subject = " ".join(str(subject).split())[:180]

    items: list[GeminiImageItem] = []
    for kind in kinds:
        if kind not in _VALID_KINDS:
            continue
        prefix = prefixes.get(kind, f"{kind}:")
        prompt = (
            f"{prefix} {subject}. Style: {signals['style']}"
            + (f", {style_sfx}" if style_sfx else "")
            + f". Environment: {signals['environment']}"
            + (f", {env_sfx}" if env_sfx else "")
            + ". High quality, video production still."
        )
        items.append(
            GeminiImageItem(
                scene_id=f"{kind}_1",
                prompt=prompt,
                style=signals["style"],
                environment=signals["environment"],
                kind=kind,  # type: ignore[arg-type]
            )
        )
    return GeminiImageBatch(items=items, notes="Heuristic image prompts.")


def _normalize_kind(raw: str) -> ImageKind:
    key = (raw or "scene").strip().lower().replace("-", "").replace("_", "")
    mapping = {
        "scene": "scene",
        "storyboard": "storyboard",
        "storyboardframe": "storyboard",
        "broll": "broll",
        "thumbnail": "thumbnail",
        "thumb": "thumbnail",
        "background": "background",
        "bg": "background",
    }
    return mapping.get(key, "scene")  # type: ignore[return-value]


def build_image_pack(
    *,
    enabled: bool = True,
    images_dir: Path | str | None = None,
    config: VideoJobConfig | None = None,
    script_pack: dict[str, Any] | None = None,
    transcript: dict[str, Any] | None = None,
    scenes: dict[str, Any] | None = None,
    stories: dict[str, Any] | None = None,
    visual_style_pack: dict[str, Any] | None = None,
    environment_pack: dict[str, Any] | None = None,
    analyze_fn: AnalyzeFn | None = None,
    generate_fn: GenerateFn | None = None,
) -> ImagePack:
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
    style = signals["style"]
    environment = signals["environment"]

    if not enabled:
        plan = ImagePlan(
            style=style,
            environment=environment,
            provider="none",
            skipped=True,
            notes="Image generation feature flag off — skipped.",
        )
        return ImagePack(source_label=style, plan=plan, notes=plan.notes)

    batch: GeminiImageBatch | None = None
    provider = "heuristic"
    notes_extra = ""
    fallback = False

    settings = get_settings()
    use_gemini = bool(analyze_fn is not None or settings.has_gemini_api_key)
    if use_gemini:
        try:
            from tools.llm.gemini import analyze_images

            fn = analyze_fn or analyze_images
            kind_hints = json.dumps(
                {
                    "default_kinds": catalog.get("default_kinds"),
                    "kind_prefixes": catalog.get("kind_prefixes"),
                },
                ensure_ascii=False,
            )
            batch = fn(
                style=style,
                environment=environment,
                audience=job.audience or "General",
                title=signals["title"],
                hook=signals["hook"],
                scene_block=signals["scene_block"],
                script_block=signals["script_block"],
                transcript_excerpt=signals["transcript_excerpt"],
                kind_hints=kind_hints,
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

    max_items = int(catalog.get("max_items") or 8)
    images_root = Path(images_dir) if images_dir else Path("images")
    images_root.mkdir(parents=True, exist_ok=True)

    gen = generate_fn or generate_image_file
    api_key = settings.gemini_api_key if settings.has_gemini_api_key else ""
    written: list[ImageAssetItem] = []
    gen_providers: list[str] = []

    for raw in list(batch.items)[:max_items]:
        kind = _normalize_kind(str(getattr(raw, "kind", "scene") or "scene"))
        scene_id = _safe_str(getattr(raw, "scene_id", "")) or f"{kind}_{len(written) + 1}"
        prompt = _safe_str(getattr(raw, "prompt", ""))
        item_style = _safe_str(getattr(raw, "style", "")) or style
        item_env = _safe_str(getattr(raw, "environment", "")) or environment
        if not prompt:
            prompt = f"{kind} visual for {signals['hook'] or signals['title'] or 'video'}"

        filename = f"{_slug(kind)}_{_slug(scene_id)}.png"
        dest = images_root / filename
        try:
            path, gen_provider = gen(prompt, dest, api_key=api_key)
        except TypeError:
            path, gen_provider = gen(prompt, dest)
        except Exception as exc:  # noqa: BLE001
            notes_extra += f" Write failed for {scene_id} ({exc})."
            continue
        gen_providers.append(gen_provider)
        written.append(
            ImageAssetItem(
                scene_id=scene_id,
                prompt=prompt,
                style=item_style,
                environment=item_env,
                image_path=str(Path(path).resolve()),
                kind=kind,
            )
        )

    if gen_providers and all(p == "placeholder" for p in gen_providers):
        asset_note = " Image files are placeholders (no Imagen/Gemini image API)."
    elif any(p in {"imagen", "gemini"} for p in gen_providers):
        asset_note = " Image files generated via API where available."
    else:
        asset_note = " Image files written under images/."

    plan = ImagePlan(
        items=written,
        style=style,
        environment=environment,
        provider=provider,
        skipped=False,
        notes=(
            f"Image plan via {provider} ({len(written)} items)."
            f"{notes_extra}{asset_note}"
        ),
    )
    return ImagePack(
        source_label=style,
        plan=plan,
        fallback=fallback,
        notes=plan.notes,
    )
