"""Run enabled moment analyzers and post-process."""

from __future__ import annotations

from typing import Any, Iterable

from core.logging import get_logger
from schemas.job import FeatureFlags
from schemas.moments import (
    CATEGORY_FLAG_MAP,
    DetectedMoment,
    MomentCategory,
)
from tools.moments.analyzers import ANALYZERS
from tools.moments.context import MomentContext, build_moment_context
from tools.moments.funny_detect import merge_funny_moments_into_detected
from tools.moments.postprocess import postprocess_moments
from tools.moments.viral_detect import merge_viral_moments_into_detected

logger = get_logger(__name__)


def enabled_categories_from_features(features: FeatureFlags | dict[str, Any]) -> list[MomentCategory]:
    if isinstance(features, dict):
        features = FeatureFlags.model_validate(features)
    enabled: list[MomentCategory] = []
    data = features.model_dump()
    for flag, category in CATEGORY_FLAG_MAP.items():
        if data.get(flag):
            enabled.append(category)
    return enabled


def run_moment_analyzers(
    *,
    enabled: Iterable[MomentCategory],
    transcript: dict[str, Any] | None = None,
    speech_transcript: dict[str, Any] | None = None,
    scenes: dict[str, Any] | None = None,
    audio_analysis: dict[str, Any] | None = None,
    speakers: dict[str, Any] | None = None,
    analysis: dict[str, Any] | None = None,
    context: MomentContext | None = None,
    funny_moments: dict[str, Any] | list[Any] | None = None,
    viral_moments: dict[str, Any] | list[Any] | None = None,
) -> list[DetectedMoment]:
    """Fuse signals via specialized analyzers; filter by enabled categories.

    When dedicated funny/viral reports are provided and those categories are
    enabled, use merged hits instead of legacy analyzers.
    """
    ctx = context or build_moment_context(
        transcript=transcript,
        speech_transcript=speech_transcript,
        scenes=scenes,
        audio_analysis=audio_analysis,
        speakers=speakers,
        analysis=analysis,
    )
    enabled_set = set(enabled)
    raw: list[DetectedMoment] = []

    use_dedicated_funny = "funny" in enabled_set and funny_moments is not None
    if use_dedicated_funny:
        raw.extend(merge_funny_moments_into_detected(funny_moments))

    use_dedicated_viral = "viral" in enabled_set and viral_moments is not None
    if use_dedicated_viral:
        raw.extend(merge_viral_moments_into_detected(viral_moments))

    for category, fn in ANALYZERS.items():
        if category not in enabled_set:
            continue
        if category == "funny" and use_dedicated_funny:
            continue
        if category == "viral" and use_dedicated_viral:
            continue
        try:
            raw.extend(fn(ctx))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Moment analyzer %s failed: %s", category, exc)

    processed = postprocess_moments(raw)
    processed = [m for m in processed if m.category in enabled_set]
    for i, m in enumerate(processed):
        m.id = i
    logger.info(
        "Moment analyzers produced %s moments across %s categories",
        len(processed),
        len({m.category for m in processed}),
    )
    return processed
