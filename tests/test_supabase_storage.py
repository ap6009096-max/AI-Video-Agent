"""Tests for local/Supabase-compatible object storage abstraction."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.errors import StorageError
from storage.local_storage import LocalObjectStorage
from storage.refs import project_object_key
from storage.supabase_storage import SupabaseObjectStorage
from storage.sync import persist_source_media, sync_project_artifacts


def test_project_isolation_keys() -> None:
    a = project_object_key("aaa", "source", "original.mp4")
    b = project_object_key("bbb", "source", "original.mp4")
    assert a == "projects/aaa/source/original.mp4"
    assert b == "projects/bbb/source/original.mp4"
    assert a != b


def test_local_upload_download_exists_delete(tmp_path: Path) -> None:
    storage = LocalObjectStorage(bucket="unit", root=tmp_path)
    src = tmp_path / "in.mp4"
    src.write_bytes(b"hello-media")
    key = "projects/p1/source/in.mp4"
    storage.upload_file(src, key)
    assert storage.file_exists(key) is True
    dest = tmp_path / "out.mp4"
    storage.download_file(key, dest)
    assert dest.read_bytes() == b"hello-media"
    url = storage.get_signed_url(key)
    assert url.startswith("file:")
    storage.delete_file(key)
    assert storage.file_exists(key) is False


def test_local_health(tmp_path: Path) -> None:
    storage = LocalObjectStorage(bucket="unit", root=tmp_path)
    ok, detail = storage.health_check()
    assert ok is True
    assert "local" in detail.lower() or "Connected" in detail


def test_persist_and_sync(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    storage = LocalObjectStorage(bucket="unit", root=tmp_path / "objects")
    monkeypatch.setattr("storage.sync.get_object_storage", lambda: storage)
    media = tmp_path / "src.mp4"
    media.write_bytes(b"source-bytes")
    ref = persist_source_media(project_id="p9", local_path=media, source_type="upload")
    assert storage.file_exists(ref.storage_path)

    project = tmp_path / "project"
    (project / "final").mkdir(parents=True)
    (project / "captions").mkdir(parents=True)
    (project / "renders" / "shorts").mkdir(parents=True)
    (project / "final" / "final.mp4").write_bytes(b"final")
    (project / "captions" / "captions.srt").write_text("1\n", encoding="utf-8")
    (project / "renders" / "shorts" / "short_30s_01.mp4").write_bytes(b"short")
    refs = sync_project_artifacts("p9", project)
    assert len(refs) >= 2
    assert any("final" in r.storage_path for r in refs)


def test_supabase_upload_with_mock_client() -> None:
    client = MagicMock()
    bucket_api = MagicMock()
    client.storage.from_.return_value = bucket_api
    bucket_api.upload.return_value = {"path": "projects/x/source/a.mp4"}
    bucket_api.create_signed_url.return_value = {
        "signedURL": "https://example.test/signed"
    }
    bucket_api.list.return_value = [{"name": "a.mp4"}]
    bucket_api.download.return_value = b"abc"

    storage = SupabaseObjectStorage(
        url="https://example.supabase.co",
        service_role_key="service-role-test-key",
        bucket="ai-video-agent",
        client=client,
    )
    # Need a real temp file for upload_file read
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as fh:
        fh.write(b"data")
        path = Path(fh.name)
    try:
        key = storage.upload_file(path, "projects/x/source/a.mp4")
        assert key.endswith("a.mp4")
        assert storage.get_signed_url(key).startswith("https://")
        assert storage.file_exists("projects/x/source/a.mp4") is True
        out = path.parent / "dl.mp4"
        storage.download_file(key, out)
        assert out.read_bytes() == b"abc"
        storage.delete_file(key)
        bucket_api.remove.assert_called()
    finally:
        path.unlink(missing_ok=True)


def test_supabase_requires_config() -> None:
    with pytest.raises(StorageError):
        SupabaseObjectStorage(url="", service_role_key="", bucket="")
