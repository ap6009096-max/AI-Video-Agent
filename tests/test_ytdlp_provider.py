"""Tests for yt-dlp YouTube provider and download provider selection."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest

from agents.youtube_agent import YouTubeAgent
from config.settings import get_settings
from core.errors import YouTubeAgentError
from schemas.base import JobStatus
from schemas.job import SourceType
from schemas.project import ProjectMetadata
from schemas.youtube import YouTubeSourceStatus
from tools.youtube.oembed_provider import OEmbedYouTubeProvider
from tools.youtube.provider import get_youtube_provider
from tools.youtube.ytdlp_provider import (
    DEFAULT_YTDLP_FORMAT,
    YtdlpYouTubeProvider,
    _default_ytdlp_download,
)

VIDEO_ID = "dQw4w9WgXcQ"
WATCH_URL = f"https://www.youtube.com/watch?v={VIDEO_ID}"


def _mock_oembed_client() -> MagicMock:
    client = MagicMock(spec=httpx.Client)

    def _get(url: str, params=None, **_kwargs):
        response = MagicMock()
        response.status_code = 200
        if "oembed" in url:
            response.json.return_value = {
                "title": "Demo Video",
                "author_name": "Demo Channel",
                "type": "video",
            }
        else:
            response.json.return_value = {"items": []}
        return response

    client.get.side_effect = _get
    return client


def test_get_youtube_provider_defaults_to_ytdlp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("YOUTUBE_DOWNLOAD_ENABLED", raising=False)
    get_settings.cache_clear()
    provider = get_youtube_provider()
    assert isinstance(provider, YtdlpYouTubeProvider)
    get_settings.cache_clear()


def test_get_youtube_provider_oembed_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("YOUTUBE_DOWNLOAD_ENABLED", "false")
    get_settings.cache_clear()
    provider = get_youtube_provider()
    assert isinstance(provider, OEmbedYouTubeProvider)
    get_settings.cache_clear()


def test_get_youtube_provider_ytdlp_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("YOUTUBE_DOWNLOAD_ENABLED", "true")
    get_settings.cache_clear()
    provider = get_youtube_provider()
    assert isinstance(provider, YtdlpYouTubeProvider)
    get_settings.cache_clear()


def test_ytdlp_provider_writes_local_media(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("YOUTUBE_DOWNLOAD_ENABLED", "true")
    get_settings.cache_clear()

    def _fake_download(url: str, source_dir: Path, options: dict) -> Path:
        assert "youtube.com" in url
        out = source_dir / f"{options['video_id']}.mp4"
        out.write_bytes(b"fake-yt-bytes")
        return out.resolve()

    meta = OEmbedYouTubeProvider(client=_mock_oembed_client())
    provider = YtdlpYouTubeProvider(metadata_provider=meta, download_fn=_fake_download)
    project_dir = tmp_path / "proj"
    fetched = provider.fetch_metadata(WATCH_URL)
    prepared = provider.prepare_source(project_dir, fetched)

    assert prepared.local_media_path is not None
    assert Path(prepared.local_media_path).is_file()
    assert prepared.metadata.source_status == YouTubeSourceStatus.READY_FOR_PIPELINE
    assert prepared.metadata.provider == "ytdlp"
    data = json.loads(Path(prepared.metadata_path).read_text(encoding="utf-8"))
    assert data["local_media_path"] == prepared.local_media_path
    get_settings.cache_clear()


def test_ytdlp_provider_propagates_download_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("YOUTUBE_DOWNLOAD_ENABLED", "true")
    get_settings.cache_clear()

    def _boom(url: str, source_dir: Path, options: dict) -> Path:
        raise YouTubeAgentError("simulated download failure")

    meta = OEmbedYouTubeProvider(client=_mock_oembed_client())
    provider = YtdlpYouTubeProvider(metadata_provider=meta, download_fn=_boom)
    fetched = provider.fetch_metadata(WATCH_URL)
    with pytest.raises(YouTubeAgentError, match="simulated download failure"):
        provider.prepare_source(tmp_path / "proj", fetched)
    get_settings.cache_clear()


def test_default_download_falls_back_from_split_format(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    formats: list[str] = []

    class _FakeYoutubeDL:
        def __init__(self, options: dict) -> None:
            self.options = options
            assert options["ffmpeg_location"]
            formats.append(str(options["format"]))

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def extract_info(self, _url: str, *, download: bool) -> dict:
            assert download is True
            if len(formats) == 1:
                raise RuntimeError("HTTP Error 403: Forbidden")
            output = Path(self.options["outtmpl"].replace("%(ext)s", "mp4"))
            output.write_bytes(b"video")
            return {"id": "fallback-video"}

        def prepare_filename(self, _info: dict) -> str:
            return str(Path(self.options["outtmpl"].replace("%(ext)s", "mp4")))

    monkeypatch.setattr(
        "tools.youtube.ytdlp_provider._require_ffmpeg_hint", lambda: None
    )
    monkeypatch.setitem(sys.modules, "yt_dlp", SimpleNamespace(YoutubeDL=_FakeYoutubeDL))

    media = _default_ytdlp_download(
        "https://www.youtube.com/watch?v=fallback-video",
        tmp_path,
        {
            "video_id": "fallback-video",
            "format": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
        },
    )

    assert media.read_bytes() == b"video"
    assert formats == [
        "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
        DEFAULT_YTDLP_FORMAT,
    ]


def test_youtube_agent_messages_include_local_media(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()

    def _fake_download(url: str, source_dir: Path, options: dict) -> Path:
        out = source_dir / "youtube_video.mp4"
        out.write_bytes(b"x")
        return out.resolve()

    meta = OEmbedYouTubeProvider(client=_mock_oembed_client())
    provider = YtdlpYouTubeProvider(metadata_provider=meta, download_fn=_fake_download)
    result = YouTubeAgent(provider=provider).run(
        ProjectMetadata(
            project_id="yt-dl-1",
            source_type=SourceType.YOUTUBE,
            youtube_url=WATCH_URL,
            status=JobStatus.RUNNING,
        ),
        project_dir=tmp_path / "outputs" / "projects" / "yt-dl-1",
    )
    assert result.local_media_path
    assert any("Local media ready" in m for m in result.messages)
    get_settings.cache_clear()
