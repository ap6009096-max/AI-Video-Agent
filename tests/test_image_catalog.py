"""Tests for image generation catalog."""

from __future__ import annotations

from pathlib import Path

from schemas.image import GeminiImageBatch, GeminiImageItem
from schemas.job import VideoJobConfig
from tools.images.catalog import build_image_pack, clear_image_cache
from tools.images.generate import write_placeholder_png


def test_flag_off_skips(tmp_path: Path) -> None:
    clear_image_cache()
    pack = build_image_pack(enabled=False, images_dir=tmp_path / "images")
    assert pack.plan.skipped is True
    assert pack.plan.items == []
    assert pack.plan.provider == "none"


def test_heuristic_writes_placeholders(tmp_path: Path) -> None:
    clear_image_cache()
    images = tmp_path / "images"
    pack = build_image_pack(
        enabled=True,
        images_dir=images,
        config=VideoJobConfig(
            visual_style="Cinematic",
            environment="Wildlife/Nature Forest",
        ),
        script_pack={
            "primary": {
                "title": "Forest tips",
                "hook": "Walk into the mist",
                "script": "Explore quiet trails at dawn.",
            }
        },
        analyze_fn=None,
        generate_fn=lambda prompt, dest, **_: (write_placeholder_png(Path(dest)), "placeholder"),
    )
    assert pack.plan.skipped is False
    assert len(pack.plan.items) >= 5
    for item in pack.plan.items:
        assert item.scene_id
        assert item.prompt
        assert item.style
        assert item.environment
        assert item.image_path
        assert Path(item.image_path).is_file()
        assert item.kind in {
            "scene",
            "storyboard",
            "broll",
            "thumbnail",
            "background",
        }


def test_inject_analyze_fn(tmp_path: Path) -> None:
    clear_image_cache()

    def _fake(**_: object) -> GeminiImageBatch:
        return GeminiImageBatch(
            items=[
                GeminiImageItem(
                    scene_id="scene_1",
                    prompt="Misty forest trail at dawn, cinematic",
                    style="Cinematic",
                    environment="Wildlife/Nature Forest",
                    kind="scene",
                )
            ]
        )

    pack = build_image_pack(
        enabled=True,
        images_dir=tmp_path / "images",
        analyze_fn=_fake,
        generate_fn=lambda prompt, dest, **_: (write_placeholder_png(Path(dest)), "placeholder"),
    )
    assert pack.plan.provider == "gemini"
    assert len(pack.plan.items) == 1
    assert pack.plan.items[0].scene_id == "scene_1"
    assert "Misty forest" in pack.plan.items[0].prompt
