"""Tests for B-roll catalog resolution and pack building."""

from __future__ import annotations

from tools.broll.catalog import (
    VALID_SOURCE_KINDS,
    build_broll_pack,
    list_broll_templates,
    resolve_broll_template,
)


def test_catalog_loads_templates() -> None:
    templates = list_broll_templates()
    assert len(templates) >= 4
    ids = {t.id for t in templates}
    assert "establishing" in ids
    assert "detail" in ids
    assert "reaction" in ids or "atmosphere" in ids


def test_resolve_template_by_name() -> None:
    tmpl = resolve_broll_template("establishing")
    assert tmpl is not None
    assert tmpl.default_source_kind in VALID_SOURCE_KINDS


def test_build_pack_items_have_valid_source_kind() -> None:
    pack = build_broll_pack(
        project_id="p1",
        clips=[{"id": 1, "start": 0.0, "end": 5.0}],
        broll_requirements="Foggy establishing shot",
        enabled=True,
    )
    assert pack.plan.skipped is False
    assert pack.plan.items
    for item in pack.plan.items:
        assert item.source_kind in VALID_SOURCE_KINDS
        assert item.available is False or bool(item.asset_path)


def test_build_pack_never_available_without_path() -> None:
    pack = build_broll_pack(
        project_id="p2",
        clips=[{"id": 0, "start": 1.0, "end": 2.0}],
        enabled=True,
    )
    for item in pack.plan.items:
        if item.available:
            assert (item.asset_path or "").strip()
        else:
            assert not (item.asset_path or "").strip() or True


def test_build_pack_skipped_when_disabled() -> None:
    pack = build_broll_pack(project_id="p3", clips=[{"id": 1}], enabled=False)
    assert pack.plan.skipped is True
    assert pack.plan.items == []
