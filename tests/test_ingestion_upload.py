"""Tests for direct upload validation and staging."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from ingestion.errors import UploadValidationError
from ingestion.upload import stage_upload_to_storage, validate_upload_bytes
from storage.factory import reset_object_storage_cache
from storage.local_storage import LocalObjectStorage


def test_validate_supported_video() -> None:
    name, mime, size = validate_upload_bytes(
        filename="clip.mp4",
        data=b"\x00\x00\x00\x18ftypmp42",
        mime_type="video/mp4",
    )
    assert name == "clip.mp4"
    assert size > 0
    assert "video" in mime or mime == "application/octet-stream"


def test_validate_supported_audio() -> None:
    name, _, size = validate_upload_bytes(
        filename="voice.mp3",
        data=b"ID3fakeaudio",
        mime_type="audio/mpeg",
    )
    assert name.endswith(".mp3")
    assert size > 0


def test_validate_unsupported_extension() -> None:
    with pytest.raises(UploadValidationError, match="Unsupported file extension"):
        validate_upload_bytes(filename="notes.exe", data=b"MZ")


def test_validate_empty_file() -> None:
    with pytest.raises(UploadValidationError, match="empty"):
        validate_upload_bytes(filename="empty.mp4", data=b"")


def test_validate_oversized_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    from config import settings as settings_mod

    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    settings_mod.get_settings.cache_clear()
    big = b"x" * (2 * 1024 * 1024)
    with pytest.raises(UploadValidationError, match="too large"):
        validate_upload_bytes(filename="big.mp4", data=big, max_upload_mb=1)
    settings_mod.get_settings.cache_clear()


def test_stage_upload_to_local_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reset_object_storage_cache()
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "")
    from config import settings as settings_mod

    settings_mod.get_settings.cache_clear()
    reset_object_storage_cache()

    storage = LocalObjectStorage(bucket="test-bucket", root=tmp_path / "objects")
    monkeypatch.setattr("ingestion.upload.get_object_storage", lambda: storage)
    monkeypatch.setattr(
        "core.paths.ensure_media_dir",
        lambda: (tmp_path / "media").mkdir(parents=True, exist_ok=True) or (tmp_path / "media"),
    )

    uploaded = SimpleNamespace(
        name="scene.mp4",
        type="video/mp4",
        getbuffer=lambda: memoryview(b"fake-video-bytes"),
    )
    ref = stage_upload_to_storage(uploaded, project_id="projA")
    assert ref.project_id == "projA"
    assert ref.storage_path.startswith("projects/projA/source/")
    assert storage.file_exists(ref.storage_path)
    assert Path(ref.local_path).is_file()
    reset_object_storage_cache()
    settings_mod.get_settings.cache_clear()
