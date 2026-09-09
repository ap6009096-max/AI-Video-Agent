"""Local video ingest — copy upload into project source/ and probe metadata."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agents.base import BaseAgent
from core.errors import InputValidationError, StorageError
from core.logging import get_logger
from core.paths import ensure_project_dir, ensure_project_source_dir
from schemas.project import ProjectMetadata
from tools.ffmpeg.probe import probe_media
from tools.project.layout import ensure_project_layout

logger = get_logger(__name__)


class LocalVideoIngestResult:
    def __init__(
        self,
        *,
        source_metadata: dict[str, Any],
        source_dir: str,
        messages: list[str],
        project: dict[str, Any] | None = None,
    ) -> None:
        self.source_metadata = source_metadata
        self.source_dir = source_dir
        self.messages = messages
        self.project = project

    def to_state_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "source_metadata": self.source_metadata,
            "source_dir": self.source_dir,
            "messages": list(self.messages),
        }
        if self.project is not None:
            out["project"] = self.project
        return out


class LocalVideoIngestAgent(BaseAgent):
    """Copy uploaded video into projects/{id}/source/ and record probe metadata."""

    name = "local_video_ingest"

    def run(
        self,
        project: ProjectMetadata | dict[str, Any],
        *,
        project_dir: str | Path | None = None,
        upload_path: str | None = None,
        **_: Any,
    ) -> LocalVideoIngestResult:
        meta = self._coerce_project(project)
        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)
        ensure_project_layout(root)
        source_dir = root / "source"
        source_dir.mkdir(parents=True, exist_ok=True)
        try:
            ensure_project_source_dir(project_id)
        except Exception:  # noqa: BLE001
            pass

        src = Path(upload_path or meta.source_path or "").expanduser()
        if not src.is_file():
            raise InputValidationError(
                f"Upload video not found: {src}"
            )

        dest = source_dir / src.name
        try:
            if src.resolve() != dest.resolve():
                shutil.copy2(src, dest)
        except OSError as exc:
            raise StorageError(f"Failed to copy upload into source/: {exc}") from exc

        probe = probe_media(dest) or {}
        duration = float(probe.get("duration") or 0.0)
        width = int(probe.get("width") or 0)
        height = int(probe.get("height") or 0)

        dest_resolved = str(dest.resolve())
        storage_fields: dict[str, Any] = {}
        try:
            from storage.sync import persist_source_media

            ref = persist_source_media(
                project_id=project_id,
                local_path=dest_resolved,
                source_type="upload",
                original_filename=dest.name,
            )
            storage_fields = {
                "storage_bucket": ref.storage_bucket,
                "storage_path": ref.storage_path,
                "original_filename": ref.original_filename,
                "file_size": ref.file_size,
                "mime_type": ref.mime_type,
                "source_status": "ready",
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Durable upload storage skipped project_id=%s err=%s",
                project_id,
                type(exc).__name__,
            )

        metadata = {
            "source_type": "upload",
            "original_path": str(src.resolve()),
            "local_path": dest_resolved,
            "media_path": dest_resolved,
            "local_media_path": dest_resolved,
            "filename": dest.name,
            "duration": duration,
            "width": width,
            "height": height,
            "video_codec": probe.get("video_codec") or "",
            "audio_codec": probe.get("audio_codec") or "",
            "has_audio": bool(probe.get("has_audio")),
            "probed_at": datetime.now(timezone.utc).isoformat(),
            **storage_fields,
        }
        meta_path = source_dir / "source_metadata.json"
        try:
            meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        except OSError as exc:
            raise StorageError(f"Failed to write source metadata: {exc}") from exc

        # Update project source_path to in-project copy
        update_payload = {"source_path": dest_resolved, **storage_fields}
        updated = meta.model_copy(update=update_payload)
        project_json = root / "project.json"
        try:
            if project_json.is_file():
                existing = json.loads(project_json.read_text(encoding="utf-8"))
            else:
                existing = updated.model_dump(mode="json")
            existing.update(update_payload)
            project_json.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not update project.json: %s", exc)
            existing = updated.model_dump(mode="json")

        messages = [
            f"[{self.name}] Copied upload → {dest_resolved}",
            f"[{self.name}] duration={duration:.2f}s {width}x{height}",
        ]
        if storage_fields.get("storage_path"):
            messages.append(
                f"[{self.name}] Durable storage → {storage_fields['storage_path']}"
            )
        logger.info(
            "LocalVideoIngest ready project_id=%s path=%s duration=%.2f",
            project_id,
            dest_resolved,
            duration,
        )
        return LocalVideoIngestResult(
            source_metadata=metadata,
            source_dir=str(source_dir),
            messages=messages,
            project=existing,
        )

    def _coerce_project(
        self, project: ProjectMetadata | dict[str, Any]
    ) -> ProjectMetadata:
        if isinstance(project, ProjectMetadata):
            return project
        try:
            return ProjectMetadata.model_validate(project)
        except Exception as exc:  # noqa: BLE001
            raise InputValidationError(f"Invalid project metadata: {exc}") from exc
