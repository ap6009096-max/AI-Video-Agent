"""Tests for storage factory fallback, hydrate, and media_ref wiring."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agents.input_agent import InputAgent
from config.settings import get_settings
from schemas.job import SourceType, VideoJobRequest
from storage.factory import (
    get_object_storage,
    reset_object_storage_cache,
    storage_config_status,
    storage_health,
)
from storage.local_storage import LocalObjectStorage
from storage.refs import MediaRef
from storage.sync import hydrate_local_media, persist_source_media


@pytest.fixture(autouse=True)
def _clear_caches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    for key in (
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_STORAGE_BUCKET",
        "SUPABASE_PUBLISHABLE_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()
    reset_object_storage_cache()
    yield
    get_settings.cache_clear()
    reset_object_storage_cache()


def test_factory_falls_back_when_supabase_unhealthy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-test")
    monkeypatch.setenv("SUPABASE_STORAGE_BUCKET", "ai-video-agent")
    get_settings.cache_clear()
    reset_object_storage_cache()

    unhealthy = MagicMock()
    unhealthy.health_check.return_value = (False, "Error: AuthApiError")
    unhealthy.backend_name = "supabase"

    with patch(
        "storage.supabase_storage.SupabaseObjectStorage",
        return_value=unhealthy,
    ):
        storage = get_object_storage()
        assert isinstance(storage, LocalObjectStorage)
        backend, ok, detail = storage_health()
        assert backend == "supabase_fallback_local"
        assert ok is False
        assert "AuthApiError" in detail or "Error" in detail
        status, status_detail = storage_config_status()
        assert status == "unreachable"


def test_factory_uses_supabase_when_healthy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-test")
    monkeypatch.setenv("SUPABASE_STORAGE_BUCKET", "ai-video-agent")
    get_settings.cache_clear()
    reset_object_storage_cache()

    healthy = MagicMock()
    healthy.health_check.return_value = (True, "Connected")
    healthy.backend_name = "supabase"

    with patch(
        "storage.supabase_storage.SupabaseObjectStorage",
        return_value=healthy,
    ):
        storage = get_object_storage()
        assert storage is healthy
        status, _ = storage_config_status()
        assert status == "configured"


def test_storage_config_status_missing() -> None:
    status, detail = storage_config_status()
    assert status == "missing"
    assert "not set" in detail.lower() or "SUPABASE" in detail


def test_hydrate_local_media_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    storage = LocalObjectStorage(bucket="unit", root=tmp_path / "objects")
    monkeypatch.setattr("storage.sync.get_object_storage", lambda: storage)
    src = tmp_path / "clip.mp4"
    src.write_bytes(b"hydrate-bytes")
    ref = persist_source_media(project_id="hyd1", local_path=src, source_type="upload")
    # Simulate missing local cache
    remote_only = MediaRef(
        project_id="hyd1",
        storage_bucket=ref.storage_bucket,
        storage_path=ref.storage_path,
        local_path="",
    )
    dest = tmp_path / "restored" / "clip.mp4"
    path = hydrate_local_media(remote_only, dest_path=dest)
    assert Path(path).is_file()
    assert Path(path).read_bytes() == b"hydrate-bytes"


def test_input_agent_copies_storage_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    media = tmp_path / "upload.mp4"
    media.write_bytes(b"x" * 64)
    request = VideoJobRequest(
        job_id="inp-storage-1",
        source_type=SourceType.UPLOAD,
        upload_path=str(media),
        storage_bucket="ai-video-agent",
        storage_path="projects/inp-storage-1/source/upload.mp4",
        original_filename="upload.mp4",
        mime_type="video/mp4",
        file_size=64,
    )
    result = InputAgent().run(request)
    project = result.project
    assert project.storage_path == "projects/inp-storage-1/source/upload.mp4"
    assert project.storage_bucket == "ai-video-agent"
    assert project.file_size == 64
    assert project.source_status == "ready"


def test_resolve_workflow_hydrates_from_job_storage_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from graph.workflow import _resolve_workflow_local_media

    storage = LocalObjectStorage(bucket="unit", root=tmp_path / "objects")
    monkeypatch.setattr("storage.sync.get_object_storage", lambda: storage)
    src = tmp_path / "from_job.mp4"
    src.write_bytes(b"job-ref-bytes")
    ref = persist_source_media(project_id="jobref", local_path=src)
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    state = {
        "project": {"project_id": "jobref"},
        "project_dir": str(project_dir),
        "job": {
            "job_id": "jobref",
            "storage_path": ref.storage_path,
            "storage_bucket": ref.storage_bucket,
        },
    }
    resolved = _resolve_workflow_local_media(state)
    assert resolved is not None
    assert Path(resolved).read_bytes() == b"job-ref-bytes"
