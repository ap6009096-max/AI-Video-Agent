"""Tests for RenderAgent multi Shorts export."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from agents.render_agent import RenderAgent
from config.settings import get_settings
from schemas.job import FeatureFlags, SourceType, VideoJobConfig
from schemas.project import ProjectMetadata


def test_render_exports_separate_shorts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    project_dir = tmp_path / "outputs" / "projects" / "rd_shorts"
    project_dir.mkdir(parents=True)
    source = project_dir / "source" / "input.mp4"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"fake-mp4")

    project = ProjectMetadata(
        project_id="rd_shorts",
        source_type=SourceType.UPLOAD,
        upload_path=str(source),
    )
    clips = {
        "multi_shorts": True,
        "clips": [
            {
                "id": 0,
                "start": 0.0,
                "end": 10.0,
                "duration": 10.0,
                "target_duration": 10,
                "transcript": "a",
                "score": 0.9,
            },
            {
                "id": 1,
                "start": 20.0,
                "end": 60.0,
                "duration": 40.0,
                "target_duration": 40,
                "transcript": "b",
                "score": 0.8,
            },
        ],
    }

    def _fake_cut(media: Path, dest: Path, *, start: float, end: float) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(f"cut-{start}-{end}".encode())
        return dest

    def _fake_concat(segments: list[Path], dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"joined")
        return dest

    def _fake_ffmpeg() -> str:
        return "ffmpeg"

    def _ok_validation(path, **_):
        from tools.media.validate_video import ValidationResult

        p = Path(path)
        return ValidationResult(
            ok=True,
            path=str(p),
            reason="ok",
            duration=1.0,
            width=1080,
            height=1920,
            fps=30.0,
            has_video=True,
            has_audio=True,
            size_bytes=p.stat().st_size if p.is_file() else 1,
        )

    encode_calls: list[dict] = []

    def _fake_encode(src: Path, dest: Path, **kwargs: object) -> Path:
        encode_calls.append({"src": src, "dest": dest, **kwargs})
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes() if src.is_file() else b"enc")
        return dest

    with (
        patch("agents.render_agent.resolve_ffmpeg_binary", _fake_ffmpeg),
        patch("agents.render_agent.cut_segment", _fake_cut),
        patch("agents.render_agent.concat_segments", _fake_concat),
        patch("agents.render_agent.encode_mp4", _fake_encode),
        patch("agents.render_agent.normalize_loudness", lambda *a, **k: None),
        patch("agents.render_agent.resize", lambda *a, **k: None),
        patch("agents.render_agent.burn_subtitles", lambda *a, **k: None),
        patch("agents.render_agent.extract_thumbnail", lambda *a, **k: None),
        patch("agents.render_agent.validate_video", side_effect=_ok_validation),
        patch.object(
            RenderAgent,
            "_resolve_source",
            lambda self, *a, **k: source,
        ),
    ):
        result = RenderAgent().run(
            project,
            project_dir=project_dir,
            config=VideoJobConfig(platform="YouTube Shorts"),
            features=FeatureFlags(multi_shorts_export=True),
            clips=clips,
        )

    plan = json.loads(Path(result.render_path).read_text(encoding="utf-8"))["plan"]
    assert plan["encoded"] is True
    assert Path(plan["output_path"]).name == "final.mp4"
    assert len(plan["short_paths"]) >= 2
    shorts_dir = project_dir / "renders" / "shorts"
    assert shorts_dir.is_dir()
    short_files = list(shorts_dir.glob("short_*.mp4"))
    assert len(short_files) >= 2
    names = {p.name for p in short_files}
    assert any(n.startswith("short_10s_") for n in names)
    assert any(n.startswith("short_40s_") for n in names)
    # Vertical package: shorts encode requests 1080x1920
    short_encodes = [
        c for c in encode_calls if c.get("width") == 1080 and c.get("height") == 1920
    ]
    assert short_encodes, "expected vertical encode dims for Shorts"
    get_settings.cache_clear()
