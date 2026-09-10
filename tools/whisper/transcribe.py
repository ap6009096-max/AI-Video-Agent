"""Local OpenAI Whisper transcription (no API key)."""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any

from config.settings import get_settings
from core.errors import TranscriptAgentError
from core.logging import get_logger
from schemas.transcript import WhisperSegment, WhisperWord

logger = get_logger(__name__)


def _running_under_streamlit() -> bool:
    """True when called from a live Streamlit script run."""
    if "streamlit" not in sys.modules:
        return False
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        return get_script_run_ctx() is not None
    except Exception:  # noqa: BLE001
        return bool(os.environ.get("STREAMLIT_SERVER_PORT") or os.environ.get("STREAMLIT_RUNTIME"))


def _is_native_block_error(exc: BaseException) -> bool:
    text = str(exc or "")
    lower = text.lower()
    return (
        "application control" in lower
        or "windows blocked" in lower
        or "dll load failed" in lower
        or "_cffiarray" in lower
        or "llvmlite" in lower
        or "numba" in lower and "blocked" in lower
    )


def _format_whisper_import_error(exc: BaseException) -> str:
    """Map import failures to actionable messages (do not claim missing when blocked)."""
    detail = str(exc or "").strip() or type(exc).__name__
    if _is_native_block_error(exc):
        return (
            "Local Whisper could not load because Windows blocked a native library "
            f"(numba/llvmlite). Detail: {detail}. "
            "Allow the DLLs under .venv\\Lib\\site-packages\\numba and llvmlite, "
            "or move the project out of OneDrive-controlled folders, then restart the app."
        )
    if "No module named" in detail and "whisper" in detail.lower():
        return "openai-whisper is not installed. Run: pip install openai-whisper"
    return f"Failed to import Whisper runtime: {detail}"


@lru_cache(maxsize=2)
def load_whisper_model(model_name: str):
    """Load and cache a local Whisper model by name."""
    try:
        import whisper  # type: ignore
    except ImportError as exc:
        raise TranscriptAgentError(_format_whisper_import_error(exc)) from exc
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


def _transcribe_subprocess(
    path: Path,
    *,
    model_name: str,
    word_timestamps: bool,
) -> dict[str, Any]:
    """Run Whisper in a fresh interpreter (avoids Streamlit-process DLL issues)."""
    out_path = Path(tempfile.mkstemp(suffix=".json", prefix="whisper_")[1])
    script = r"""
import json, sys
import whisper
model_name, media, out, words = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] == "1"
model = whisper.load_model(model_name)
raw = model.transcribe(media, word_timestamps=words, verbose=False)
# Make JSON-safe
def clean(obj):
    if isinstance(obj, dict):
        return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean(x) for x in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)
with open(out, "w", encoding="utf-8") as fh:
    json.dump(clean(raw), fh)
"""
    cmd = [
        sys.executable,
        "-c",
        script,
        model_name,
        str(path),
        str(out_path),
        "1" if word_timestamps else "0",
    ]
    env = os.environ.copy()
    # Prefer project venv site-packages when launched oddly
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60 * 30,
            cwd=str(Path(__file__).resolve().parents[2]),
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise TranscriptAgentError("Whisper subprocess timed out.") from exc

    if completed.returncode != 0:
        err = (completed.stderr or completed.stdout or "").strip()[:500]
        raise TranscriptAgentError(
            _format_whisper_import_error(Exception(err or "Whisper subprocess failed"))
        )

    try:
        raw = json.loads(out_path.read_text(encoding="utf-8"))
    finally:
        try:
            out_path.unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass
    if not isinstance(raw, dict):
        raise TranscriptAgentError("Whisper subprocess returned invalid JSON.")
    return raw


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
    raw: dict[str, Any] | None = None
    prefer_subprocess = _running_under_streamlit()

    if prefer_subprocess:
        # Windows Application Control has blocked numba._cffiarray inside the
        # Streamlit process; a fresh interpreter avoids that failure mode.
        try:
            raw = _transcribe_subprocess(
                path, model_name=name, word_timestamps=word_timestamps
            )
        except TranscriptAgentError as exc:
            logger.warning(
                "Streamlit Whisper subprocess failed (%s); trying in-process",
                exc,
            )
            prefer_subprocess = False

    if raw is None:
        try:
            model = load_whisper_model(name)
            raw = model.transcribe(
                str(path), word_timestamps=word_timestamps, verbose=False
            )
        except TranscriptAgentError as exc:
            if _is_native_block_error(exc) or "Failed to import Whisper" in str(exc):
                logger.warning(
                    "In-process Whisper failed (%s); retrying in subprocess",
                    exc,
                )
                try:
                    load_whisper_model.cache_clear()
                except Exception:  # noqa: BLE001
                    pass
                raw = _transcribe_subprocess(
                    path, model_name=name, word_timestamps=word_timestamps
                )
            else:
                raise
        except Exception as exc:  # noqa: BLE001
            if _is_native_block_error(exc):
                logger.warning(
                    "In-process Whisper native block (%s); retrying in subprocess",
                    exc,
                )
                try:
                    load_whisper_model.cache_clear()
                except Exception:  # noqa: BLE001
                    pass
                raw = _transcribe_subprocess(
                    path, model_name=name, word_timestamps=word_timestamps
                )
            else:
                logger.exception("Whisper transcription failed")
                raise TranscriptAgentError(
                    f"Whisper transcription failed: {exc}"
                ) from exc

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
