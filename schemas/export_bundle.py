"""Export bundle schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ExportBundle(BaseModel):
    video_path: str = ""
    thumbnail_path: str = ""
    caption_paths: list[str] = Field(default_factory=list)
    platform_metadata_path: str = ""
    manifest_path: str = ""
    notes: str = ""


class ExportPack(BaseModel):
    project_id: str = ""
    bundle: ExportBundle = Field(default_factory=ExportBundle)
    export_path: str = ""
    skipped: bool = False
    output_files: dict[str, Any] = Field(default_factory=dict)
    notes: str = ""
    created_at: datetime = Field(default_factory=_utc_now)


class ExportResult(BaseModel):
    export_pack: ExportPack
    export_manifest_path: str
    messages: list[str] = Field(default_factory=list)

    def to_state_dict(self) -> dict[str, Any]:
        return {
            "export_pack": self.export_pack.model_dump(mode="json"),
            "messages": list(self.messages),
        }
