"""Tests for avatar catalog."""

from __future__ import annotations

from tools.avatar.catalog import build_avatar_pack, list_avatars, resolve_avatar
from schemas.job import VideoJobConfig


REQUIRED = [
    "No Avatar",
    "Male presenter",
    "Female presenter",
    "Business presenter",
    "Teacher",
    "News anchor",
    "Influencer",
    "Custom avatar",
]


def test_catalog_loads_all_presets() -> None:
    names = {p.name for p in list_avatars()}
    missing = [n for n in REQUIRED if n not in names]
    assert not missing, f"Missing: {missing}"


def test_resolve_presenters() -> None:
    for name in REQUIRED[1:]:
        preset = resolve_avatar(name)
        assert preset is not None
        assert preset.name == name


def test_build_enabled_teacher() -> None:
    pack = build_avatar_pack(
        "Teacher",
        enabled=True,
        config=VideoJobConfig(
            avatar="Teacher",
            language="English",
            voice="AI Voice",
            voice_emotion="calm",
        ),
    )
    assert pack.plan.skipped is False
    assert pack.plan.avatar_type == "Teacher"
    assert pack.plan.lip_sync is True
    assert pack.plan.eye_contact is True
    assert pack.plan.gesture == "point"
    assert pack.plan.language == "English"
    assert pack.plan.emotion == "calm"


def test_build_disabled_skips() -> None:
    pack = build_avatar_pack("Male presenter", enabled=False)
    assert pack.plan.skipped is True
    assert pack.plan.lip_sync is False
