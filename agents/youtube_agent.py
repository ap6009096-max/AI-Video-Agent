"""YouTube Agent — validate URLs, fetch metadata, prepare source package."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agents.base import BaseAgent
from core.errors import StorageError, YouTubeAgentError
from core.logging import get_logger
from core.paths import ensure_project_dir, ensure_project_source_dir
from schemas.project import ProjectMetadata
from schemas.youtube import YouTubeAgentResult
from tools.youtube.provider import YouTubeSourceProvider, get_youtube_provider

logger = get_logger(__name__)


class YouTubeAgent(BaseAgent):
    """Prepare authorized YouTube source metadata for the understanding pipeline."""

    name = "youtube"

    def __init__(self, provider: YouTubeSourceProvider | None = None) -> None:
        self.provider = provider or get_youtube_provider()

    def run(
        self,
        project: ProjectMetadata | dict[str, Any],
        project_dir: str | Path | None = None,
        **_: Any,
    ) -> YouTubeAgentResult:
        """Validate URL, fetch metadata, write source/, return LangGraph state."""
        meta = self._coerce_project(project)
        url = (meta.youtube_url or "").strip()
        if not url:
            raise YouTubeAgentError("Project is missing youtube_url.")

        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        # Ensure source parent exists even before provider prepare
        ensure_project_source_dir(project_id)

        try:
            canonical = self.provider.normalize_url(url)
            fetched = self.provider.fetch_metadata(url)
            prepared = self.provider.prepare_source(root, fetched)
        except YouTubeAgentError:
            raise
        except StorageError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise YouTubeAgentError(f"YouTube agent failed: {exc}") from exc

        media_msg = (
            f"[{self.name}] Local media ready → {prepared.local_media_path}"
            if prepared.local_media_path
            else (
                f"[{self.name}] Local media not downloaded; "
                "set YOUTUBE_DOWNLOAD_ENABLED=true for yt-dlp, or upload a video."
            )
        )
        messages = [
            f"[{self.name}] Validated URL → {canonical}",
            f"[{self.name}] Title: {prepared.metadata.title or '(unknown)'}",
            f"[{self.name}] Channel: {prepared.metadata.channel or '(unknown)'}",
            (
                f"[{self.name}] Duration: "
                f"{prepared.metadata.duration_seconds if prepared.metadata.duration_seconds is not None else 'unknown'}s"
            ),
            f"[{self.name}] Source status: {prepared.metadata.source_status.value}",
            media_msg,
            f"[{self.name}] Passing source to video understanding pipeline.",
        ]
        logger.info(
            "YouTubeAgent ready project_id=%s video_id=%s status=%s",
            project_id,
            prepared.metadata.video_id,
            prepared.metadata.source_status.value,
        )
        return YouTubeAgentResult(
            metadata=prepared.metadata,
            source_dir=prepared.source_dir,
            metadata_path=prepared.metadata_path,
            local_media_path=prepared.local_media_path,
            messages=messages,
        )

    def _coerce_project(self, project: ProjectMetadata | dict[str, Any]) -> ProjectMetadata:
        if isinstance(project, ProjectMetadata):
            return project
        try:
            return ProjectMetadata.model_validate(project)
        except Exception as exc:  # noqa: BLE001
            raise YouTubeAgentError(f"Invalid project metadata: {exc}") from exc
