"""Object storage protocol and shared helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from storage.refs import MediaRef, path_safe_name, project_object_key


@runtime_checkable
class ObjectStorage(Protocol):
    """Durable object storage used by ingestion and render sync."""

    @property
    def bucket(self) -> str: ...

    @property
    def backend_name(self) -> str: ...

    def upload_file(
        self,
        local_path: str | Path,
        storage_path: str,
        *,
        content_type: str | None = None,
        upsert: bool = True,
    ) -> str: ...

    def download_file(self, storage_path: str, dest_path: str | Path) -> Path: ...

    def get_signed_url(self, storage_path: str, *, expires_in: int = 3600) -> str: ...

    def delete_file(self, storage_path: str) -> None: ...

    def file_exists(self, storage_path: str) -> bool: ...

    def health_check(self) -> tuple[bool, str]: ...


def upload_project_file(
    storage: ObjectStorage,
    *,
    project_id: str,
    category: str,
    local_path: str | Path,
    filename: str | None = None,
    content_type: str | None = None,
) -> MediaRef:
    """Upload a local file into ``projects/{id}/{category}/...`` and return a MediaRef."""
    path = Path(local_path)
    if not path.is_file():
        raise FileNotFoundError(f"Local file missing for upload: {path}")
    name = path_safe_name(filename or path.name)
    key = project_object_key(project_id, category, name)
    storage.upload_file(path, key, content_type=content_type, upsert=True)
    return MediaRef(
        project_id=project_id,
        storage_bucket=storage.bucket,
        storage_path=key,
        local_path=str(path.resolve()),
        mime_type=content_type or "",
        file_size=int(path.stat().st_size),
        original_filename=name,
        status="ready",
    )


__all__ = [
    "ObjectStorage",
    "upload_project_file",
    "MediaRef",
    "project_object_key",
    "path_safe_name",
]
