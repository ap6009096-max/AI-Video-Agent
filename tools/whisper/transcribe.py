"""Local OpenAI Whisper transcription (no API key)."""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path
from typing import Any

from config.settings import get_settings
from core.errors import TranscriptAgentError
from core.logging import get_logger
from schemas.transcript import WhisperSegment, WhisperWord

logger = get_logger(__name__)


@lru_cache(maxsize=2)
def load_whisper_model(model_name: str):
    """Load and cache a local Whisper model by name."""
    try:
        import whisper  # type: ignore
    except ImportError as exc:
        raise TranscriptAgentError(
            "openai-whisper is not installed. Run: pip install openai-whisper"
        ) from exc
    logger.info("Loading local Whisper model=%s", model_name)
    return whisper.load_model(model_name)


def _logprob_to_confidence(avg_logprob: float | None) -> float | None:
    if avg_logprob is None:
        return None
    try:
        # Map log-prob to (0, 1) roughly
        return float(1.0 / (1.0 + math.exp(-avg_logprob)))
    except Exception:  # noqa: BLE001
        return None


def normalize_whisper_result(raw: dict[str, Any]) -> tuple[str, list[WhisperSegment]]:
    """Convert Whisper raw result into language + normalized segments."""
    language = str(raw.get("language") or "").strip()
    segments: list[WhisperSegment] = []
    for idx, seg in enumerate(raw.get("segments") or []):
        words: list[WhisperWord] = []
        for w in seg.get("words") or []:
            word_text = str(w.get("word") or "").strip()
            if not word_text:
                continue
            words.append(
                WhisperWord(
                    word=word_text,
                    start=float(w.get("start") or 0.0),
                    end=float(w.get("end") or 0.0),
                    probability=(
                        float(w["probability"])
                        if w.get("probability") is not None
                        else None
                    ),
                )
            )
        avg_logprob = seg.get("avg_logprob")
        avg_logprob_f = float(avg_logprob) if avg_logprob is not None else None
        text = str(seg.get("text") or "").strip()
        segments.append(
            WhisperSegment(
                id=int(seg.get("id", idx)),
                start=float(seg.get("start") or 0.0),
                end=float(seg.get("end") or 0.0),
                text=text,
                words=words,
                avg_logprob=avg_logprob_f,
                confidence=_logprob_to_confidence(avg_logprob_f),
            )
        )
    return language, segments


def transcribe_media(
    media_path: str | Path,
    *,
    model_name: str | None = None,
    word_timestamps: bool = True,
) -> dict[str, Any]:
    """Run local Whisper on a media/audio path.

    Returns a dict with keys: language, text, segments (WhisperSegment list),
    model, raw (original whisper result).
    """
    path = Path(media_path)
    if not path.is_file():
        raise TranscriptAgentError(f"Cannot transcribe missing file: {path}")

    name = model_name or get_settings().whisper_model
    try:
        model = load_whisper_model(name)
        raw = model.transcribe(str(path), word_timestamps=word_timestamps, verbose=False)
    except TranscriptAgentError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Whisper transcription failed")
        raise TranscriptAgentError(f"Whisper transcription failed: {exc}") from exc

    if not isinstance(raw, dict):
        raise TranscriptAgentError("Unexpected Whisper return type.")

    language, segments = normalize_whisper_result(raw)
    text = str(raw.get("text") or "").strip()
    if not text and segments:
        text = " ".join(s.text for s in segments if s.text).strip()

    return {
        "language": language,
        "text": text,
        "segments": segments,
        "model": name,
        "raw": raw,
    }
