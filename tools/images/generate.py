"""Write PNG image files (Gemini/Imagen when available, else placeholder)."""

from __future__ import annotations

import base64
from pathlib import Path

from core.logging import get_logger

logger = get_logger(__name__)

# 1x1 PNG — used when live image generation is unavailable
_PLACEHOLDER_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def write_placeholder_png(dest: Path) -> Path:
    """Write a minimal valid PNG placeholder."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(_PLACEHOLDER_PNG)
    return dest.resolve()


def generate_image_file(
    prompt: str,
    dest: Path,
    *,
    api_key: str = "",
) -> tuple[Path, str]:
    """Generate an image file at ``dest``.

    Returns ``(path, provider)`` where provider is ``gemini``, ``imagen``,
    or ``placeholder``.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    key = (api_key or "").strip()
    if key:
        try:
            path, provider = _try_gemini_image(prompt, dest, key)
            if path is not None:
                return path, provider
        except Exception as exc:  # noqa: BLE001
            logger.warning("Image generation API failed (%s); using placeholder", exc)

    write_placeholder_png(dest)
    return dest.resolve(), "placeholder"


def _try_gemini_image(
    prompt: str, dest: Path, api_key: str
) -> tuple[Path | None, str]:
    """Best-effort Gemini / Imagen call; returns (None, _) when unsupported."""
    try:
        from google import genai  # type: ignore[import-untyped]
        from google.genai import types  # type: ignore[import-untyped]
    except ImportError:
        return None, "none"

    client = genai.Client(api_key=api_key)
    # Prefer Imagen when available; fall back to placeholder on any failure.
    try:
        result = client.models.generate_images(
            model="imagen-3.0-generate-002",
            prompt=(prompt or "abstract visual")[:2000],
            config=types.GenerateImagesConfig(number_of_images=1),
        )
        generated = getattr(result, "generated_images", None) or []
        if not generated:
            return None, "none"
        first = generated[0]
        image = getattr(first, "image", None)
        data = getattr(image, "image_bytes", None) if image is not None else None
        if not data:
            return None, "none"
        dest.write_bytes(data)
        return dest.resolve(), "imagen"
    except Exception:  # noqa: BLE001
        return None, "none"
