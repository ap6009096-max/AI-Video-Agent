"""Integration tests for full pipeline + fixture media."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from agents.local_video_ingest_agent import LocalVideoIngestAgent
from config.settings import get_settings
from schemas.job import FeatureFlags, SourceType, VideoJobConfig, VideoJobRequest
from schemas.project import ProjectMetadata
from tools.ffmpeg.bin import resolve_ffmpeg_binary
from tools.project.layout import finalize_project_layout


FIXTURES = Path(__file__).resolve().parent / "fixtures"
SAMPLE_MP4 = FIXTURES / "sample.mp4"


def _ensure_sample_mp4() -> Path:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    if SAMPLE_MP4.is_file() and SAMPLE_MP4.stat().st_size > 0:
        return SAMPLE_MP4
    ffmpeg = resolve_ffmpeg_binary()
    if ffmpeg:
        cmd = [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=320x240:d=1",
            "-f",
            "lavfi",
            "-i",
            "sine=f=440:d=1",
            "-shortest",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            str(SAMPLE_MP4),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode == 0 and SAMPLE_MP4.is_file():
            return SAMPLE_MP4
    # Minimal placeholder so path-based tests still run without FFmpeg
    SAMPLE_MP4.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom")
    return SAMPLE_MP4


@pytest.mark.integration
def test_local_ingest_and_layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sample = _ensure_sample_mp4()
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "int1"
    project_dir.mkdir(parents=True)
    project = ProjectMetadata(
        project_id="int1",
        source_type=SourceType.UPLOAD,
        source_path=str(sample),
    )
    result = LocalVideoIngestAgent().run(
        project, project_dir=project_dir, upload_path=str(sample)
    )
    assert Path(result.source_metadata["local_path"]).is_file()
    assert Path(result.source_metadata["local_media_path"]).is_file()
    assert result.source_metadata["local_media_path"] == result.source_metadata["local_path"]
    assert result.source_metadata["media_path"] == result.source_metadata["local_path"]
    assert result.project is not None
    assert result.project["source_path"] == result.source_metadata["local_media_path"]
    assert (project_dir / "source").is_dir()

    (project_dir / "analysis").mkdir(exist_ok=True)
    (project_dir / "analysis" / "video_analysis.json").write_text("{}", encoding="utf-8")
    (project_dir / "analysis" / "scenes.json").write_text("{}", encoding="utf-8")
    (project_dir / "analysis" / "moments.json").write_text("{}", encoding="utf-8")
    (project_dir / "analysis" / "clips.json").write_text("{}", encoding="utf-8")
    (project_dir / "analysis" / "quality_report.json").write_text(
        '{"passed":true}', encoding="utf-8"
    )
    out = finalize_project_layout(project_dir)
    assert (project_dir / "analysis.json").is_file()
    assert (project_dir / "video_plan.json").is_file()
    assert out["aliases"]
    get_settings.cache_clear()


@pytest.mark.integration
def test_upload_request_shape() -> None:
    sample = _ensure_sample_mp4()
    req = VideoJobRequest(
        source_type=SourceType.UPLOAD,
        upload_path=str(sample),
        config=VideoJobConfig(),
        features=FeatureFlags(viral_moments=False, funny_moments=False),
    )
    assert req.upload_path.endswith("sample.mp4")
