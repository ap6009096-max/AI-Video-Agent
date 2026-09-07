"""Transcript Agent — local Whisper speech-to-text for project media."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from agents.base import BaseAgent
from config.settings import get_settings
from core.errors import StorageError, TranscriptAgentError
from core.logging import get_logger
from core.paths import (
    ensure_project_dir,
    ensure_project_transcripts_dir,
    get_speech_transcript_path,
)
from schemas.job import ALLOWED_UPLOAD_EXTENSIONS
from schemas.project import ProjectMetadata
from schemas.transcript import (
    TranscriptAgentResult,
    WhisperSegment,
    WhisperTranscript,
)
from tools.audio.ffmpeg_audio import extract_wav_for_asr, require_media_file
from tools.media.resolve import validate_media_path
from tools.whisper.adapter import whisper_to_structured
from tools.whisper.transcribe import transcribe_media

logger = get_logger(__name__)

TranscribeFn = Callable[..., dict[str, Any]]


class TranscriptAgent(BaseAgent):
    """Extract timed speech transcript from local video/audio using Whisper."""

    name = "transcript"

    def __init__(self, transcribe_fn: TranscribeFn | None = None) -> None:
        self._transcribe_fn = transcribe_fn or transcribe_media

    def run(
        self,
        project: ProjectMetadata | dict[str, Any],
        *,
        project_dir: str | Path | None = None,
        source_metadata: dict[str, Any] | None = None,
        **_: Any,
    ) -> TranscriptAgentResult:
        meta = self._coerce_project(project)
        media_path = self._resolve_media_path(meta, source_metadata)
        logger.info("[TRANSCRIPTION] Starting transcription")
        logger.info("[MEDIA] Local path: %s", media_path)
        media = require_media_file(media_path)
        self._validate_extension(media)

        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        transcripts_dir = root / "transcripts"
        transcripts_dir.mkdir(parents=True, exist_ok=True)
        try:
            ensure_project_transcripts_dir(project_id)
        except Exception:  # noqa: BLE001 — custom roots in tests may differ
            pass

        asr_input = media
        wav = extract_wav_for_asr(media, transcripts_dir / "audio.wav")
        if wav is not None:
            asr_input = wav

        try:
            result = self._transcribe_fn(asr_input)
        except TranscriptAgentError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise TranscriptAgentError(f"Transcription failed: {exc}") from exc

        segments = result.get("segments") or []
        if segments and isinstance(segments[0], dict):
            segments = [WhisperSegment.model_validate(s) for s in segments]

        model_name = str(result.get("model") or get_settings().whisper_model)
        speech = WhisperTranscript(
            project_id=project_id,
            source_type=meta.source_type,
            media_path=str(media),
            language=str(result.get("language") or ""),
            segments=list(segments),
            text=str(result.get("text") or "").strip(),
            provider="whisper-local",
            model=model_name,
        )
        if not speech.text and not speech.segments:
            raise TranscriptAgentError("Whisper returned an empty transcript.")

        path = self._write_speech_transcript(project_id, root, speech)
        structured = whisper_to_structured(speech)

        messages = [
            f"[{self.name}] Media: {media.name}",
            f"[{self.name}] Language: {speech.language or 'unknown'}",
            f"[{self.name}] Segments: {len(speech.segments)}",
            f"[{self.name}] Words timed: {sum(1 for s in speech.segments if s.words)}",
            f"[{self.name}] Model: {speech.model} (local, no API key)",
            f"[{self.name}] Wrote transcripts/transcript.json",
        ]
        logger.info(
            "TranscriptAgent ready project_id=%s segments=%s language=%s",
            project_id,
            len(speech.segments),
            speech.language,
        )
        logger.info("[TRANSCRIPTION] Transcript generated")
        return TranscriptAgentResult(
            speech_transcript=speech,
            structured_transcript=structured,
            transcript_path=str(path),
            messages=messages,
        )

    def _coerce_project(self, project: ProjectMetadata | dict[str, Any]) -> ProjectMetadata:
        if isinstance(project, ProjectMetadata):
            return project
        try:
            return ProjectMetadata.model_validate(project)
        except Exception as exc:  # noqa: BLE001
            raise TranscriptAgentError(f"Invalid project metadata: {exc}") from exc

    def _resolve_media_path(
        self,
        meta: ProjectMetadata,
        source_metadata: dict[str, Any] | None,
    ) -> str:
        candidates: list[str] = []
        if meta.source_path:
            candidates.append(meta.source_path)
        if source_metadata:
            for key in ("local_media_path", "media_path", "local_path"):
                local = source_metadata.get(key)
                if local:
                    candidates.append(str(local))
        for path in candidates:
            try:
                return validate_media_path(path)
            except (ValueError, FileNotFoundError, OSError):
                continue
        raise TranscriptAgentError(
            "No local media file available for transcription. "
            "Upload a video, or provide an authorized local_media_path. "
            "YouTube metadata-only sources cannot be transcribed without local media."
        )

    def _validate_extension(self, media: Path) -> None:
        ext = media.suffix.lower()
        # Allow common audio extracts too
        allowed = ALLOWED_UPLOAD_EXTENSIONS | {".wav", ".mp3", ".m4a", ".flac"}
        if ext not in allowed:
            raise TranscriptAgentError(
                f"Unsupported media format '{ext}'. "
                f"Allowed: {', '.join(sorted(allowed))}"
            )

    def _write_speech_transcript(
        self,
        project_id: str,
        root: Path,
        speech: WhisperTranscript,
    ) -> Path:
        path = root / "transcripts" / "transcript.json"
        try:
            canonical = get_speech_transcript_path(project_id)
            if canonical.parent.parent == root.resolve() or root.resolve() == canonical.parent.parent:
                path = canonical
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(speech.model_dump(mode="json"), indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            raise StorageError(f"Failed to write speech transcript: {path}") from exc
        return path.resolve()
