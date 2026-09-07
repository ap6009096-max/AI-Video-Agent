"""Load B-roll templates and build honest B-roll plans."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from schemas.av_plan import BRollItem, BRollPack, BRollPlan, BRollTemplate

_CATALOG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "broll.json"

VALID_SOURCE_KINDS = frozenset(
    {
        "source_footage",
        "user_provided",
        "external_required",
        "generated_required",
        "placeholder",
    }
)


def _norm(value: str) -> str:
    return " ".join(
        (value or "").strip().lower().replace("_", " ").replace("-", " ").split()
    )


@lru_cache(maxsize=1)
def _load_raw() -> dict[str, Any]:
    return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))


def clear_broll_cache() -> None:
    _load_raw.cache_clear()


def list_broll_templates() -> list[BRollTemplate]:
    raw = _load_raw().get("templates") or []
    return [BRollTemplate.model_validate(item) for item in raw]


def resolve_broll_template(name_or_id: str) -> BRollTemplate | None:
    key = _norm(name_or_id)
    if not key:
        return None
    for tmpl in list_broll_templates():
        if _norm(tmpl.id) == key or _norm(tmpl.name) == key:
            return tmpl
        for alias in tmpl.aliases:
            if _norm(alias) == key:
                return tmpl
    return None


def build_broll_pack(
    *,
    project_id: str,
    clips: list[dict[str, Any]] | None = None,
    broll_requirements: str = "",
    enabled: bool = True,
) -> BRollPack:
    if not enabled:
        plan = BRollPlan(
            project_id=project_id,
            items=[],
            skipped=True,
            notes="B-roll planning skipped (feature flag off).",
        )
        return BRollPack(plan=plan, notes=plan.notes)

    clip_list = clips or []
    templates = list_broll_templates()
    by_id = {t.id: t for t in templates}
    establishing = by_id.get("establishing") or templates[0]
    atmosphere = by_id.get("atmosphere") or establishing
    detail = by_id.get("detail") or establishing

    items: list[BRollItem] = []
    if not clip_list:
        items.append(
            BRollItem(
                clip_id=0,
                description=broll_requirements
                or establishing.description
                or "Environment establishing B-roll",
                source_kind="placeholder",
                available=False,
                template_id=establishing.id,
                notes="No clips selected — placeholder only; footage not available.",
            )
        )
    else:
        for clip in clip_list:
            try:
                clip_id = int(clip.get("id", 0))
            except (TypeError, ValueError):
                clip_id = 0
            start = clip.get("start")
            end = clip.get("end")
            try:
                start_f = float(start) if start is not None else None
                end_f = float(end) if end is not None else None
            except (TypeError, ValueError):
                start_f, end_f = None, None

            # Atmosphere / env-driven cutaway — not assumed present
            kind = atmosphere.default_source_kind
            if kind not in VALID_SOURCE_KINDS:
                kind = "external_required"
            desc = (
                broll_requirements.strip()
                if broll_requirements.strip()
                else atmosphere.description
            )
            items.append(
                BRollItem(
                    clip_id=clip_id,
                    description=desc,
                    start_hint=start_f,
                    end_hint=end_f,
                    source_kind=kind,
                    available=False,
                    template_id=atmosphere.id,
                    notes=(
                        "Planned from environment/template; "
                        "asset not available until acquired or generated."
                    ),
                )
            )
            # Detail placeholder
            dkind = detail.default_source_kind
            if dkind not in VALID_SOURCE_KINDS:
                dkind = "placeholder"
            items.append(
                BRollItem(
                    clip_id=clip_id,
                    description=detail.description,
                    start_hint=start_f,
                    end_hint=end_f,
                    source_kind=dkind,
                    available=False,
                    template_id=detail.id,
                    notes="Detail insert planned; not available without an asset path.",
                )
            )

    plan = BRollPlan(
        project_id=project_id,
        items=items,
        skipped=False,
        notes=(
            f"Planned {len(items)} B-roll item(s). "
            "Never treat items as available without a real asset_path."
        ),
    )
    return BRollPack(plan=plan, notes=plan.notes)
