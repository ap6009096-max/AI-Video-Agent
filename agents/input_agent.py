"""Input Agent — detect, validate, and initialize video projects."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from agents.base import BaseAgent
from config.settings import get_settings
from core.errors import InputValidationError, StorageError
from core.logging import get_logger
from core.paths import ensure_project_dir
from tools.project.layout import ensure_project_layout
from schemas.base import JobStatus
from schemas.job import ALLOWED_UPLOAD_EXTENSIONS, SourceType, VideoJobRequest
from schemas.project import (
    SOURCE_TO_ROUTE,
    DownstreamRoute,
    InputAgentResult,
    ProjectMetadata,
)

logger = get_logger(__name__)


class InputAgent(BaseAgent):
    """Validate user input, create project metadata, and route downstream."""

    name = "input"

    def run(self, request: VideoJobRequest | dict[str, Any], **_: Any) -> InputAgentResult:
        """Detect source, validate, persist project.json, and return LangGraph state."""
        job = self._coerce_request(request)
        source_type = self._detect_source_type(job)
        self._validate(job, source_type)

        project_id = (job.job_id or "").strip() or str(uuid4())
        project_dir = ensure_project_dir(project_id)
        ensure_project_layout(project_dir)

        metadata = ProjectMetadata(
            project_id=project_id,
            source_type=source_type,
            source_path=job.upload_path if source_type == SourceType.UPLOAD else "",
            youtube_url=job.youtube_url if source_type == SourceType.YOUTUBE else "",
            raw_text=(
                job.script_text
                if source_type in (SourceType.SCRIPT, SourceType.IDEA)
                else ""
            ),
            storage_bucket=str(job.storage_bucket or ""),
            storage_path=str(job.storage_path or ""),
            original_filename=str(job.original_filename or ""),
            mime_type=str(job.mime_type or ""),
            file_size=int(job.file_size or 0),
            source_status="ready" if job.storage_path else "",
            status=JobStatus.RUNNING,
            configuration={
                "config": job.config.model_dump(mode="json"),
                "features": job.features.model_dump(mode="json"),
            },
        )
        self._write_project_json(project_dir, metadata)

        next_agent = SOURCE_TO_ROUTE[source_type]
        messages = [
            f"[{self.name}] Detected source type: {source_type.value}",
            f"[{self.name}] Project initialized: {project_id}",
            f"[{self.name}] Routing to: {next_agent.value}",
        ]
        logger.info(
            "InputAgent ready project_id=%s source=%s route=%s",
            project_id,
            source_type.value,
            next_agent.value,
        )
        return InputAgentResult(
            project=metadata,
            project_dir=str(project_dir),
            next_agent=next_agent,
            messages=messages,
            detected_source_type=source_type,
        )

    def _coerce_request(self, request: VideoJobRequest | dict[str, Any]) -> VideoJobRequest:
        if isinstance(request, VideoJobRequest):
            return request
        try:
            return VideoJobRequest.model_validate(request)
        except Exception as exc:  # noqa: BLE001 — normalize to InputValidationError
            raise InputValidationError(f"Invalid job request: {exc}") from exc

    def _detect_source_type(self, job: VideoJobRequest) -> SourceType:
        """Confirm and return the declared source type."""
        if job.source_type not in SourceType:
            raise InputValidationError(f"Unknown source type: {job.source_type!r}")
        return job.source_type

    def _validate(self, job: VideoJobRequest, source_type: SourceType) -> None:
        if source_type == SourceType.YOUTUBE:
            self._validate_youtube_url(job.youtube_url)
        elif source_type == SourceType.UPLOAD:
            self._validate_upload(job.upload_path)
        elif source_type == SourceType.SCRIPT:
            self._validate_script(job.script_text)
        elif source_type == SourceType.IDEA:
            self._validate_script(job.script_text)
        else:
            raise InputValidationError(f"Unsupported source type: {source_type}")

    def _validate_youtube_url(self, url: str) -> None:
        raw = (url or "").strip()
        if not raw:
            raise InputValidationError("YouTube URL is required.")
        parsed = urlparse(raw)
        if parsed.scheme not in {"http", "https"}:
            raise InputValidationError("YouTube URL must start with http:// or https://.")
        host = (parsed.netloc or "").lower()
        if "youtube.com" not in host and "youtu.be" not in host:
            raise InputValidationError(
                "URL must be a valid YouTube link (youtube.com or youtu.be)."
            )
        if "youtu.be" in host and not (parsed.path or "").strip("/"):
            raise InputValidationError("YouTube short URL is missing a video id.")

    def _validate_upload(self, upload_path: str) -> None:
        if not (upload_path or "").strip():
            raise InputValidationError("Uploaded video path is required.")
        path = Path(upload_path)
        if not path.is_file():
            raise InputValidationError(f"Upload file not found: {path}")
        ext = path.suffix.lower()
        if ext not in ALLOWED_UPLOAD_EXTENSIONS:
            raise InputValidationError(
                f"Unsupported upload format '{ext}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_UPLOAD_EXTENSIONS))}"
            )
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise InputValidationError(f"Unable to read upload file: {path}") from exc
        if size <= 0:
            raise InputValidationError("Upload file is empty.")
        max_mb = get_settings().max_upload_mb
        max_bytes = max_mb * 1024 * 1024
        if size > max_bytes:
            raise InputValidationError(
                f"Upload exceeds maximum size of {max_mb} MB "
                f"({size / (1024 * 1024):.1f} MB provided)."
            )

    def _validate_script(self, text: str) -> None:
        if not (text or "").strip():
            raise InputValidationError("Script text is required.")

    def _write_project_json(self, project_dir: Path, metadata: ProjectMetadata) -> Path:
        path = project_dir / "project.json"
        try:
            path.write_text(
                json.dumps(metadata.model_dump(mode="json"), indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            raise StorageError(f"Failed to write project metadata: {path}") from exc
        logger.debug("Wrote project metadata to %s", path)
        return path


def route_for_source(source_type: SourceType) -> DownstreamRoute:
    """Map a source type to its downstream ingest route."""
    return SOURCE_TO_ROUTE[source_type]
