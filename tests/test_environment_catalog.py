"""Tests for environment catalog resolution."""

from __future__ import annotations

from tools.environments.catalog import (
    build_environment_pack,
    environment_prompt_block,
    list_environments,
    resolve_environment,
)


REQUIRED_NAMES = [
    "Enchanted Forest",
    "Magical Forest",
    "Ancient Forest",
    "Foggy Forest",
    "Moonlit Forest",
    "Fairy Forest",
    "Mushroom Fantasy Forest",
    "Fairy-Tale Forest",
    "Mountain Forest",
    "Rainy Forest",
    "Sunrise Forest",
    "Golden-Hour Forest",
    "Winter Forest",
    "Autumn Forest",
    "Fantasy Tropical Forest",
    "Cosmic Forest",
    "Fantasy Kingdom",
    "Dragon Fantasy",
    "Wildlife/Nature Forest",
    "Magical Wizard Forest",
]


def test_catalog_loads_all_twenty() -> None:
    envs = list_environments()
    names = {e.name for e in envs}
    assert len(REQUIRED_NAMES) == 20
    missing = [n for n in REQUIRED_NAMES if n not in names]
    assert not missing, f"Missing presets: {missing}"
    assert len(envs) == 20


def test_resolve_key_environments() -> None:
    enchanted = resolve_environment("Enchanted Forest")
    assert enchanted is not None
    assert "glow" in enchanted.visual_description.lower() or enchanted.lighting
    foggy = resolve_environment("foggy forest")
    assert foggy is not None
    assert foggy.name == "Foggy Forest"
    kingdom = resolve_environment("Fantasy Kingdom")
    assert kingdom is not None
    assert kingdom.background_requirements


def test_legacy_mixed_to_wildlife() -> None:
    preset = resolve_environment("Mixed")
    assert preset is not None
    assert preset.name == "Wildlife/Nature Forest"
    pack = build_environment_pack("Mixed")
    assert pack.fallback is False
    assert pack.preset.name == "Wildlife/Nature Forest"
    assert pack.plan.summary


def test_legacy_indoor_to_kingdom() -> None:
    assert resolve_environment("Indoor").name == "Fantasy Kingdom"
    assert resolve_environment("Studio").name == "Fantasy Kingdom"
    assert resolve_environment("Urban").name == "Fantasy Kingdom"
    assert resolve_environment("Nature").name == "Wildlife/Nature Forest"
    assert resolve_environment("Outdoor").name == "Wildlife/Nature Forest"


def test_unknown_soft_fallback() -> None:
    pack = build_environment_pack("Totally Unknown Place XYZ")
    assert pack.fallback is True
    assert pack.plan.summary
    block = environment_prompt_block(pack)
    assert "Environment:" in block
    assert "B-roll requirements:" in block
