"""Tests for music catalog resolution."""

from __future__ import annotations

from tools.music.catalog import build_music_pack, list_music_presets, resolve_music


REQUIRED_MOODS = [
    "Original Audio",
    "No Music",
    "Background Music",
    "Dramatic",
    "Cinematic",
    "Funny",
    "Energetic",
    "Emotional",
    "Educational",
]


def test_catalog_loads_all_moods() -> None:
    presets = list_music_presets()
    names = {p.name for p in presets}
    missing = [n for n in REQUIRED_MOODS if n not in names]
    assert not missing, f"Missing moods: {missing}"
    for preset in presets:
        assert preset.generation_required is False


def test_resolve_key_moods() -> None:
    dramatic = resolve_music("Dramatic")
    assert dramatic is not None
    assert dramatic.mode == "bed"
    none = resolve_music("No Music")
    assert none is not None
    assert none.mode == "none"


def test_build_pack_generation_never_required() -> None:
    for name in REQUIRED_MOODS:
        pack = build_music_pack(name, enabled=True)
        assert pack.plan.generation_required is False
        assert pack.preset.generation_required is False
        assert pack.plan.asset_path == ""


def test_unknown_soft_fallback() -> None:
    pack = build_music_pack("Totally Unknown Score XYZ", enabled=True)
    assert pack.fallback is True
    assert pack.plan.generation_required is False
