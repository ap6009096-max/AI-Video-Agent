"""Tests for the YouTube Agent and oEmbed provider (mocked HTTP)."""

from __future__ import annotations

import json
from pathlib import Path
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
from tools.youtube.oembed_provider import OEmbedYouTubeProvider, parse_iso8601_duration


VIDEO_ID = "dQw4w9WgXcQ"
WATCH_URL = f"https://www.youtube.com/watch?v={VIDEO_ID}"


def _mock_client(oembed_payload: dict, data_api_payload: dict | None = None) -> MagicMock:
    client = MagicMock(spec=httpx.Client)

    def _get(url: str, params=None, **_kwargs):
        response = MagicMock()
        if "oembed" in url:
            response.status_code = 200
            response.json.return_value = oembed_payload
        elif "googleapis.com" in url:
            response.status_code = 200
            response.json.return_value = data_api_payload or {"items": []}
        else:
            response.status_code = 404
            response.json.return_value = {}
        return response

    client.get.side_effect = _get
    return client


def test_parse_iso8601_duration() -> None:
    assert parse_iso8601_duration("PT1H2M10S") == 3730.0
    assert parse_iso8601_duration("PT45S") == 45.0
    assert parse_iso8601_duration("P1DT2H") == 93600.0
    assert parse_iso8601_duration("bad") is None


def test_youtube_agent_writes_source_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    get_settings.cache_clear()

    client = _mock_client(
        {"title": "Demo Video", "author_name": "Demo Channel", "type": "video"}
    )
    provider = OEmbedYouTubeProvider(client=client)
    agent = YouTubeAgent(provider=provider)

    project = ProjectMetadata(
        project_id="yt-proj-1",
        source_type=SourceType.YOUTUBE,
        youtube_url=WATCH_URL,
        status=JobStatus.RUNNING,
    )
    result = agent.run(project, project_dir=tmp_path / "outputs" / "projects" / "yt-proj-1")

    assert result.metadata.title == "Demo Video"
    assert result.metadata.channel == "Demo Channel"
    assert result.metadata.video_id == VIDEO_ID
    assert result.metadata.url == WATCH_URL
    assert result.metadata.duration_seconds is None
    assert result.metadata.source_status == YouTubeSourceStatus.AWAITING_AUTHORIZED_MEDIA
    assert result.local_media_path is None

    meta_path = Path(result.metadata_path)
    assert meta_path.is_file()
    data = json.loads(meta_path.read_text(encoding="utf-8"))
    assert data["title"] == "Demo Video"
    assert data["channel"] == "Demo Channel"
    assert data["source_status"] == "awaiting_authorized_media"
    assert "duration_seconds" in data
    assert (Path(result.source_dir) / "README.md").is_file()

    state = result.to_state_dict()
    assert state["source_metadata"]["local_media_path"] is None
    assert "project" not in state

    get_settings.cache_clear()


def test_youtube_agent_result_to_state_dict_with_local_media(tmp_path: Path) -> None:
    from schemas.youtube import YouTubeAgentResult, YouTubeSourceMetadata

    media = tmp_path / "source" / "video.mp4"
    media.parent.mkdir(parents=True, exist_ok=True)
    media.write_bytes(b"fake")
    result = YouTubeAgentResult(
        metadata=YouTubeSourceMetadata(
            url=WATCH_URL,
            canonical_url=WATCH_URL,
            video_id=VIDEO_ID,
            title="T",
            channel="C",
            source_status=YouTubeSourceStatus.READY_FOR_PIPELINE,
            provider="test",
        ),
        source_dir=str(tmp_path / "source"),
        metadata_path=str(tmp_path / "source" / "source_metadata.json"),
        local_media_path=str(media),
        messages=[],
    )
    state = result.to_state_dict()
    assert state["source_metadata"]["local_media_path"] == str(media)


def test_youtube_agent_duration_with_api_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    get_settings.cache_clear()

    client = _mock_client(
        {"title": "Timed", "author_name": "Chan"},
        data_api_payload={
            "items": [{"contentDetails": {"duration": "PT3M5S"}}],
        },
    )
    provider = OEmbedYouTubeProvider(client=client)
    result = YouTubeAgent(provider=provider).run(
        ProjectMetadata(
            project_id="yt-dur",
            source_type=SourceType.YOUTUBE,
            youtube_url=WATCH_URL,
        ),
        project_dir=tmp_path / "proj",
    )
    assert result.metadata.duration_seconds == 185.0
    get_settings.cache_clear()


def test_youtube_agent_oembed_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()

    client = MagicMock(spec=httpx.Client)
    response = MagicMock()
    response.status_code = 404
    client.get.return_value = response

    provider = OEmbedYouTubeProvider(client=client)
    with pytest.raises(YouTubeAgentError, match="not found|unavailable"):
        YouTubeAgent(provider=provider).run(
            ProjectMetadata(
                project_id="yt-miss",
                source_type=SourceType.YOUTUBE,
                youtube_url=WATCH_URL,
            ),
            project_dir=tmp_path / "proj",
        )
    get_settings.cache_clear()
