"""Local filesystem object storage (tests / offline durable mirror)."""

from __future__ import annotations

import shutil
import time
from pathlib import Path
from urllib.parse import quote

from core.errors import StorageError
from core.logging import get_logger
from core.paths import get_output_dir

logger = get_logger(__name__)


class LocalObjectStorage:
    """Mirror Supabase key layout under ``OUTPUT_DIR/objects/{bucket}/``."""

    def __init__(self, *, bucket: str = "local", root: Path | None = None) -> None:
        self._bucket = (bucket or "local").strip() or "local"
        base = root if root is not None else (get_output_dir() / "objects")
        self._root = Path(base).expanduser().resolve() / self._bucket
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def bucket(self) -> str:
        return self._bucket

    @property
    def backend_name(self) -> str:
        return "local"

    def _abs(self, storage_path: str) -> Path:
        key = str(storage_path or "").lstrip("/\\").replace("\\", "/")
        if not key or ".." in key.split("/"):
            raise StorageError(f"Invalid storage path: {storage_path!r}")
        return (self._root / key).resolve()

    def upload_file(
        self,
        local_path: str | Path,
        storage_path: str,
        *,
        content_type: str | None = None,
        upsert: bool = True,
    ) -> str:
        _ = content_type
        src = Path(local_path)
        if not src.is_file():
            raise StorageError(f"Upload source missing: {src}")
        dest = self._abs(storage_path)
        if dest.exists() and not upsert:
            raise StorageError(f"Object already exists: {storage_path}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(src, dest)
        except OSError as exc:
            raise StorageError(f"Local upload failed: {storage_path}") from exc
        logger.info("STORAGE_UPLOAD_SUCCEEDED backend=local path=%s", storage_path)
        return storage_path

    def download_file(self, storage_path: str, dest_path: str | Path) -> Path:
        src = self._abs(storage_path)
        if not src.is_file():
            raise StorageError(f"Object not found: {storage_path}")
        dest = Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(src, dest)
        except OSError as exc:
            raise StorageError(f"Local download failed: {storage_path}") from exc
        return dest.resolve()

    def get_signed_url(self, storage_path: str, *, expires_in: int = 3600) -> str:
        path = self._abs(storage_path)
        if not path.is_file():
            raise StorageError(f"Object not found: {storage_path}")
        # file:// URLs for local preview; expires_in unused but kept for API parity
        _ = expires_in
        return path.as_uri() + f"?exp={int(time.time()) + max(1, expires_in)}&p={quote(storage_path)}"

    def delete_file(self, storage_path: str) -> None:
        path = self._abs(storage_path)
        if path.is_file():
            path.unlink()

    def file_exists(self, storage_path: str) -> bool:
        try:
            return self._abs(storage_path).is_file()
        except StorageError:
            return False

    def health_check(self) -> tuple[bool, str]:
        try:
            self._root.mkdir(parents=True, exist_ok=True)
            probe = self._root / ".health"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return True, "Connected (local mirror)"
        except OSError as exc:
            return False, f"Error: {exc}"
