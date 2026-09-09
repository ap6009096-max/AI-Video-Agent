"""Durable project media storage (Supabase or local mirror)."""

from __future__ import annotations

from storage.base import ObjectStorage, upload_project_file
from storage.factory import (
    get_object_storage,
    reset_object_storage_cache,
    storage_config_status,
    storage_health,
)
from storage.refs import MediaRef, path_safe_name, project_object_key
from storage.sync import (
    hydrate_local_media,
    persist_source_media,
    signed_url_for,
    sync_project_artifacts,
)

__all__ = [
    "ObjectStorage",
    "MediaRef",
    "get_object_storage",
    "reset_object_storage_cache",
    "storage_health",
    "storage_config_status",
    "upload_project_file",
    "project_object_key",
    "path_safe_name",
    "hydrate_local_media",
    "persist_source_media",
    "signed_url_for",
    "sync_project_artifacts",
]
