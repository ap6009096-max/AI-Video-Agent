"""Supabase Storage backend (server-side service role only)."""

from __future__ import annotations

import mimetypes
import time
from pathlib import Path
from typing import Any

from core.errors import StorageError
from core.logging import get_logger

logger = get_logger(__name__)


class SupabaseObjectStorage:
    """Upload/download/signed-URL operations against a private Supabase bucket."""

    def __init__(
        self,
        *,
        url: str,
        service_role_key: str,
        bucket: str,
        client: Any | None = None,
    ) -> None:
        self._url = (url or "").strip().rstrip("/")
        self._key = (service_role_key or "").strip()
        self._bucket = (bucket or "").strip()
        if not self._url or not self._key or not self._bucket:
            raise StorageError(
                "Supabase storage requires SUPABASE_URL, "
                "SUPABASE_SERVICE_ROLE_KEY, and SUPABASE_STORAGE_BUCKET."
            )
        self._client = client
        if self._client is None:
            try:
                from supabase import create_client
            except ImportError as exc:  # pragma: no cover
                raise StorageError(
                    "supabase package is not installed. Run: pip install supabase"
                ) from exc
            self._client = create_client(self._url, self._key)

    @property
    def bucket(self) -> str:
        return self._bucket

    @property
    def backend_name(self) -> str:
        return "supabase"

    def _storage(self) -> Any:
        return self._client.storage.from_(self._bucket)

    def upload_file(
        self,
        local_path: str | Path,
        storage_path: str,
        *,
        content_type: str | None = None,
        upsert: bool = True,
    ) -> str:
        src = Path(local_path)
        if not src.is_file():
            raise StorageError(f"Upload source missing: {src}")
        key = str(storage_path or "").lstrip("/")
        mime = content_type or mimetypes.guess_type(src.name)[0] or "application/octet-stream"
        data = src.read_bytes()
        file_options: dict[str, str] = {"content-type": mime}
        if upsert:
            file_options["upsert"] = "true"

        last_error: Exception | None = None
        for attempt in range(3):
            try:
                logger.info("UPLOAD_STARTED backend=supabase path=%s", key)
                self._storage().upload(key, data, file_options=file_options)
                logger.info("STORAGE_UPLOAD_SUCCEEDED backend=supabase path=%s", key)
                return key
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                # Retry transient failures with exponential backoff
                msg = str(exc).lower()
                retryable = any(
                    token in msg
                    for token in ("timeout", "temporarily", "503", "502", "429", "connection")
                )
                if not retryable or attempt >= 2:
                    break
                time.sleep(2**attempt)
        raise StorageError(f"Supabase upload failed for {key}: {last_error}") from last_error

    def download_file(self, storage_path: str, dest_path: str | Path) -> Path:
        key = str(storage_path or "").lstrip("/")
        dest = Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            raw = self._storage().download(key)
        except Exception as exc:  # noqa: BLE001
            raise StorageError(f"Supabase download failed for {key}: {exc}") from exc
        if isinstance(raw, memoryview):
            raw = raw.tobytes()
        if not isinstance(raw, (bytes, bytearray)):
            raise StorageError(f"Unexpected download payload for {key}")
        dest.write_bytes(bytes(raw))
        return dest.resolve()

    def get_signed_url(self, storage_path: str, *, expires_in: int = 3600) -> str:
        key = str(storage_path or "").lstrip("/")
        try:
            response = self._storage().create_signed_url(key, expires_in)
        except Exception as exc:  # noqa: BLE001
            raise StorageError(f"Signed URL failed for {key}: {exc}") from exc
        if isinstance(response, dict):
            url = (
                response.get("signedURL")
                or response.get("signedUrl")
                or response.get("signed_url")
                or (response.get("data") or {}).get("signedUrl")
                or (response.get("data") or {}).get("signedURL")
            )
            if url:
                return str(url)
        # Newer clients may return objects with attributes
        for attr in ("signed_url", "signedURL", "signedUrl"):
            if hasattr(response, attr) and getattr(response, attr):
                return str(getattr(response, attr))
        raise StorageError(f"Signed URL missing in response for {key}")

    def delete_file(self, storage_path: str) -> None:
        key = str(storage_path or "").lstrip("/")
        try:
            self._storage().remove([key])
        except Exception as exc:  # noqa: BLE001
            raise StorageError(f"Supabase delete failed for {key}: {exc}") from exc

    def file_exists(self, storage_path: str) -> bool:
        key = str(storage_path or "").lstrip("/")
        parent = str(Path(key).parent).replace("\\", "/")
        name = Path(key).name
        if parent in {".", ""}:
            parent = ""
        try:
            listing = self._storage().list(parent or "")
        except Exception:
            return False
        items = listing if isinstance(listing, list) else getattr(listing, "data", None) or []
        for item in items:
            if isinstance(item, dict) and item.get("name") == name:
                return True
            if getattr(item, "name", None) == name:
                return True
        return False

    def health_check(self) -> tuple[bool, str]:
        try:
            # Lightweight list of bucket root; does not expose secrets
            self._storage().list("")
            return True, "Connected"
        except Exception as exc:  # noqa: BLE001
            return False, f"Error: {type(exc).__name__}"
