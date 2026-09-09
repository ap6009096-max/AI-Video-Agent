"""Media artifact references (paths/keys — never embed binary in state)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


def path_safe_name(filename: str) -> str:
    name = Path(str(filename or "file.bin")).name
    return name or "file.bin"


def project_object_key(project_id: str, category: str, filename: str) -> str:
    """Build ``projects/{id}/{category}/{filename}`` storage key."""
    pid = str(project_id or "").strip().strip("/\\")
    cat = str(category or "misc").strip().strip("/\\")
    name = path_safe_name(filename)
    if not pid:
        raise ValueError("project_id is required for storage keys")
    return f"projects/{pid}/{cat}/{name}"


@dataclass(slots=True)
class MediaRef:
    """Reference to a durable object plus optional local working cache path."""

    project_id: str
    storage_bucket: str
    storage_path: str
    local_path: str = ""
    mime_type: str = ""
    file_size: int = 0
    original_filename: str = ""
    source_type: str = ""
    source_url: str = ""
    status: str = "ready"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> MediaRef | None:
        if not isinstance(data, dict):
            return None
        project_id = str(data.get("project_id") or "").strip()
        storage_path = str(data.get("storage_path") or "").strip()
        if not project_id or not storage_path:
            return None
        return cls(
            project_id=project_id,
            storage_bucket=str(data.get("storage_bucket") or data.get("bucket") or ""),
            storage_path=storage_path,
            local_path=str(data.get("local_path") or ""),
            mime_type=str(data.get("mime_type") or ""),
            file_size=int(data.get("file_size") or 0),
            original_filename=str(data.get("original_filename") or ""),
            source_type=str(data.get("source_type") or ""),
            source_url=str(data.get("source_url") or ""),
            status=str(data.get("status") or "ready"),
        )
