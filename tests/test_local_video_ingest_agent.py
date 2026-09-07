"""Unit tests for local upload ingest media path contract."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from agents.local_video_ingest_agent import LocalVideoIngestAgent
from config.settings import get_settings
from schemas.base import JobStatus
from schemas.job import SourceType
from schemas.project import ProjectMetadata


def test_local_video_ingest_sets_local_media_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()

    upload = tmp_path / "clip.mp4"
    upload.write_bytes(b"fake-video")
    project_dir = tmp_path / "outputs" / "projects" / "lv1"
    project = ProjectMetadata(
        project_id="lv1",
        source_type=SourceType.UPLOAD,
        source_path=str(upload),
        status=JobStatus.RUNNING,
    )

    with patch(
        "agents.local_video_ingest_agent.probe_media",
        return_value={
            "duration": 1.5,
            "width": 640,
            "height": 360,
            "has_audio": True,
        },
    ):
        result = LocalVideoIngestAgent().run(
            project, project_dir=project_dir, upload_path=str(upload)
        )

    local = result.source_metadata["local_media_path"]
    assert Path(local).is_file()
    assert result.source_metadata["local_path"] == local
    assert result.source_metadata["media_path"] == local
    assert result.project is not None
    assert result.project["source_path"] == local
    get_settings.cache_clear()
