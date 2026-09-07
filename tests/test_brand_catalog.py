"""Tests for brand catalog / pack builder."""

from __future__ import annotations

import pytest

from config.settings import get_settings
from schemas.brand import GeminiBrandBatch
from schemas.job import VideoJobConfig
from tools.brand.catalog import (
    build_brand_pack,
    clear_brand_cache,
    resolve_brand_preset,
)


@pytest.fixture(autouse=True)
def _clear(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    get_settings.cache_clear()
    clear_brand_cache()
    yield
    get_settings.cache_clear()
    clear_brand_cache()


def test_resolve_brand_presets() -> None:
    assert resolve_brand_preset("Generic Creator") is not None
    assert resolve_brand_preset("corporate_clean") is not None
    assert resolve_brand_preset("Bold Lifestyle") is not None


def test_build_public_domains_and_colors() -> None:
    pack = build_brand_pack(
        enabled=True,
        config=VideoJobConfig(brand_preset="Corporate Clean", brand_name="Acme Co"),
    )
    plan = pack.plan
    assert plan.skipped is False
    assert plan.brand_name == "Acme Co"
    assert plan.voice.tone
    assert plan.visual_identity.typography
    assert plan.colors.primary.startswith("#")
    assert plan.colors.secondary.startswith("#")
    assert plan.cta.style
    assert plan.messaging.tagline
    assert plan.messaging.pillars


def test_skipped_empty() -> None:
    pack = build_brand_pack(enabled=False, config=VideoJobConfig())
    assert pack.plan.skipped is True
    assert pack.plan.provider == "none"
    assert pack.plan.voice.tone == ""
    assert pack.plan.colors.primary == ""


def test_visual_style_blends_into_usage_notes() -> None:
    pack = build_brand_pack(
        enabled=True,
        config=VideoJobConfig(brand_preset="generic_creator"),
        visual_style_pack={
            "plan": {"color_palette": "warm earth tones"},
        },
    )
    assert "warm earth tones" in pack.plan.colors.usage_notes


def test_enrich_fn_injection() -> None:
    def _enrich(**_: object) -> GeminiBrandBatch:
        return GeminiBrandBatch(
            tone="crisp",
            personality="mentor",
            tagline="Ship clear stories",
            preferred_phrases=["Learn more"],
            pillars=["Trust"],
            notes="enriched",
        )

    pack = build_brand_pack(
        enabled=True,
        config=VideoJobConfig(brand_preset="Corporate Clean"),
        enrich_fn=_enrich,
    )
    assert pack.plan.provider == "gemini"
    assert pack.plan.voice.tone == "crisp"
    assert pack.plan.messaging.tagline == "Ship clear stories"
    assert "enriched" in pack.plan.notes
