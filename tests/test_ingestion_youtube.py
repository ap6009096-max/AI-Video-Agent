"""Tests for YouTube ingestion error classification and download wrapper."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from ingestion.errors import (
    YouTubeDownloadError,
    YouTubeDownloadStatus,
    classify_ytdlp_error,
    user_message_for_status,
    user_message_for_youtube_error,
)
from ingestion.youtube import (
    PROGRESSIVE_FORMAT,
    _build_format_chain,
    _cleanup_partials,
    _error_warrants_auth_retry,
    _format_needs_ffmpeg,
    _resolve_local_youtube_auth,
    download_youtube,
)


def _settings(**overrides: object) -> MagicMock:
    settings = MagicMock()
    settings.youtube_download_enabled = True
    settings.youtube_download_format = "bv*+ba/b"
    settings.youtube_cookies_file = ""
    settings.youtube_cookies_from_browser = ""
    settings.youtube_auth_fallback = True
    settings.ffmpeg_path = ""
    settings.is_streamlit_cloud = False
    settings.app_env = "test"
    settings.log_level = "INFO"
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


def test_classify_403() -> None:
    err = classify_ytdlp_error(Exception("HTTP Error 403: Forbidden"))
    assert err.status == YouTubeDownloadStatus.FORBIDDEN
    assert err.code == "forbidden"
    assert err.retryable is False


def test_classify_unavailable() -> None:
    err = classify_ytdlp_error(Exception("ERROR: [youtube] abc: Video unavailable"))
    assert err.status == YouTubeDownloadStatus.UNAVAILABLE


def test_classify_private() -> None:
    err = classify_ytdlp_error(Exception("Private video. Sign in if you've been granted access"))
    assert err.status in {
        YouTubeDownloadStatus.RESTRICTED,
        YouTubeDownloadStatus.AUTHENTICATION_REQUIRED,
    }


def test_classify_network_retryable() -> None:
    err = classify_ytdlp_error(Exception("URLError: timed out"))
    assert err.status == YouTubeDownloadStatus.NETWORK_ERROR
    assert err.retryable is True


def test_user_message_forbidden_mentions_upload() -> None:
    err = YouTubeDownloadError(
        "forbidden",
        "YouTube rejected the media request with HTTP 403.",
        status=YouTubeDownloadStatus.FORBIDDEN,
    )
    msg = user_message_for_youtube_error(err)
    assert "403" in msg or "blocked" in msg.lower()
    assert "upload" in msg.lower()
    assert "Technical detail" in msg


def test_user_message_auth_mentions_upload_pipeline() -> None:
    err = YouTubeDownloadError(
        "authentication_required",
        "YouTube requires authentication to access this video.",
        status=YouTubeDownloadStatus.AUTHENTICATION_REQUIRED,
    )
    msg = user_message_for_youtube_error(err)
    assert "authentication" in msg.lower()
    assert "upload" in msg.lower()
    assert "pipeline" in msg.lower()


def test_user_message_for_status_restricted() -> None:
    msg = user_message_for_status(YouTubeDownloadStatus.RESTRICTED)
    assert "upload" in msg.lower()


def test_format_chain_merge_first_when_ffmpeg() -> None:
    from ingestion.youtube import HTTPS_MERGE_FORMAT, MERGE_FORMAT

    chain = _build_format_chain("bv*+ba/b", ffmpeg_available=True)
    assert chain[0] == HTTPS_MERGE_FORMAT
    assert MERGE_FORMAT in chain
    assert PROGRESSIVE_FORMAT in chain
    assert _format_needs_ffmpeg("bv*+ba/b") is True
    assert _format_needs_ffmpeg(PROGRESSIVE_FORMAT) is False


def test_format_chain_no_merge_without_ffmpeg() -> None:
    chain = _build_format_chain("bv*+ba/b", ffmpeg_available=False)
    assert all("+" not in fmt for fmt in chain)
    assert PROGRESSIVE_FORMAT in chain


def test_classify_format_unavailable() -> None:
    err = classify_ytdlp_error(
        Exception(
            "ERROR: [youtube] abc: Requested format is not available. "
            "Use --list-formats for a list of available formats"
        )
    )
    assert err.status == YouTubeDownloadStatus.EXTRACTOR_ERROR


def test_invalid_url() -> None:
    result = download_youtube("not-a-url")
    assert result.ok is False
    assert result.error is not None
    assert result.error.status == YouTubeDownloadStatus.EXTRACTOR_ERROR


def test_empty_url() -> None:
    result = download_youtube("")
    assert result.ok is False
    assert result.error is not None


def test_download_success_mocked(tmp_path: Path) -> None:
    media = tmp_path / "vid123.mp4"
    fake_info = {"title": "Demo", "id": "vid123"}
    seen: list[dict[str, object]] = []

    def _run(url, source_dir, **kwargs):  # noqa: ANN001
        seen.append(
            {
                "cookies_file": kwargs.get("cookies_file") or "",
                "cookies_from_browser": kwargs.get("cookies_from_browser") or "",
            }
        )
        media.write_bytes(b"fake-mp4-bytes-not-empty")
        return media, fake_info

    with (
        patch("ingestion.youtube.get_settings", return_value=_settings()),
        patch("ingestion.youtube._resolve_ffmpeg", return_value="/usr/bin/ffmpeg"),
        patch("tools.youtube.urls.normalize_youtube_url", return_value="https://youtu.be/vid123"),
        patch("tools.youtube.urls.extract_video_id", return_value="vid123"),
        patch("ingestion.youtube._run_ytdlp", side_effect=_run),
    ):
        result = download_youtube(
            "https://www.youtube.com/watch?v=vid123",
            dest_dir=tmp_path,
        )
    assert result.ok is True
    assert Path(result.local_path).is_file()
    assert seen
    assert all(not c["cookies_file"] and not c["cookies_from_browser"] for c in seen)


def test_progressive_succeeds_without_ffmpeg(tmp_path: Path) -> None:
    media = tmp_path / "prog1.mp4"
    fake_info = {"title": "Prog", "id": "prog1"}
    seen_formats: list[str] = []

    def _run(url, source_dir, **kwargs):  # noqa: ANN001
        seen_formats.append(kwargs.get("format_value") or "")
        assert not _format_needs_ffmpeg(kwargs["format_value"])
        media.write_bytes(b"progressive-bytes")
        return media, fake_info

    with (
        patch(
            "ingestion.youtube.get_settings",
            return_value=_settings(youtube_download_format=PROGRESSIVE_FORMAT),
        ),
        patch("ingestion.youtube._resolve_ffmpeg", return_value=""),
        patch("tools.youtube.urls.normalize_youtube_url", return_value="https://youtu.be/prog1"),
        patch("tools.youtube.urls.extract_video_id", return_value="prog1"),
        patch("ingestion.youtube._run_ytdlp", side_effect=_run),
    ):
        result = download_youtube("https://youtu.be/prog1", dest_dir=tmp_path)

    assert result.ok is True
    assert seen_formats
    assert all(not _format_needs_ffmpeg(f) for f in seen_formats)


def test_download_403_does_not_raise(tmp_path: Path) -> None:
    with (
        patch(
            "ingestion.youtube.get_settings",
            return_value=_settings(youtube_auth_fallback=False),
        ),
        patch("ingestion.youtube._resolve_ffmpeg", return_value="/usr/bin/ffmpeg"),
        patch("tools.youtube.urls.normalize_youtube_url", return_value="https://youtu.be/x"),
        patch("tools.youtube.urls.extract_video_id", return_value="x"),
        patch(
            "ingestion.youtube._run_ytdlp",
            side_effect=YouTubeDownloadError(
                "forbidden",
                "YouTube rejected the media request with HTTP 403.",
                retryable=False,
                status=YouTubeDownloadStatus.FORBIDDEN,
            ),
        ),
    ):
        result = download_youtube("https://youtu.be/x", dest_dir=tmp_path)
    assert result.ok is False
    assert result.error is not None
    assert result.error.status == YouTubeDownloadStatus.FORBIDDEN
    assert "upload" in user_message_for_youtube_error(result.error).lower()


def test_cleanup_partials_removes_artifacts(tmp_path: Path) -> None:
    partial = tmp_path / "vid999.mp4.part"
    partial.write_bytes(b"partial")
    done = tmp_path / "vid999.mp4"
    done.write_bytes(b"x")
    other = tmp_path / "other.mp4"
    other.write_bytes(b"keep")
    _cleanup_partials(tmp_path, "vid999")
    assert not partial.exists()
    assert not done.exists()
    assert other.exists()


def test_failed_attempt_cleans_partials(tmp_path: Path) -> None:
    calls = {"n": 0}

    def _boom(url, source_dir, **kwargs):  # noqa: ANN001
        calls["n"] += 1
        junk = Path(source_dir) / "z.mp4"
        junk.write_bytes(b"partial-download")
        raise YouTubeDownloadError(
            "forbidden",
            "YouTube rejected the media request with HTTP 403.",
            retryable=False,
            status=YouTubeDownloadStatus.FORBIDDEN,
        )

    with (
        patch(
            "ingestion.youtube.get_settings",
            return_value=_settings(
                youtube_download_format=PROGRESSIVE_FORMAT,
                youtube_auth_fallback=False,
            ),
        ),
        patch("ingestion.youtube._resolve_ffmpeg", return_value="/bin/ffmpeg"),
        patch("tools.youtube.urls.normalize_youtube_url", return_value="https://youtu.be/z"),
        patch("tools.youtube.urls.extract_video_id", return_value="z"),
        patch("ingestion.youtube._run_ytdlp", side_effect=_boom),
    ):
        result = download_youtube("https://youtu.be/z", dest_dir=tmp_path)

    assert result.ok is False
    assert not (tmp_path / "z.mp4").exists()
    assert calls["n"] >= 1


def test_auth_retry_uses_browser_after_authentication_required(tmp_path: Path) -> None:
    media = tmp_path / "auth1.mp4"
    fake_info = {"title": "Auth", "id": "auth1"}
    calls: list[dict[str, str]] = []

    def _run(url, source_dir, **kwargs):  # noqa: ANN001
        cookies_file = str(kwargs.get("cookies_file") or "")
        browser = str(kwargs.get("cookies_from_browser") or "")
        calls.append({"cookies_file": cookies_file, "browser": browser})
        if not browser and not cookies_file:
            raise YouTubeDownloadError(
                "authentication_required",
                "YouTube requires authentication to access this video.",
                retryable=False,
                status=YouTubeDownloadStatus.AUTHENTICATION_REQUIRED,
            )
        media.write_bytes(b"authed-bytes")
        return media, fake_info

    with (
        patch(
            "ingestion.youtube.get_settings",
            return_value=_settings(
                youtube_download_format=PROGRESSIVE_FORMAT,
                youtube_cookies_from_browser="chrome",
                youtube_auth_fallback=True,
            ),
        ),
        patch("ingestion.youtube._resolve_ffmpeg", return_value="/bin/ffmpeg"),
        patch("tools.youtube.urls.normalize_youtube_url", return_value="https://youtu.be/auth1"),
        patch("tools.youtube.urls.extract_video_id", return_value="auth1"),
        patch("ingestion.youtube._run_ytdlp", side_effect=_run),
    ):
        result = download_youtube("https://youtu.be/auth1", dest_dir=tmp_path)

    assert result.ok is True
    assert any(c["browser"] == "" and c["cookies_file"] == "" for c in calls)
    assert any(c["browser"] == "chrome" for c in calls)


def test_cookies_file_wins_over_browser(tmp_path: Path) -> None:
    cookie = tmp_path / "cookies.txt"
    cookie.write_text("# Netscape\n", encoding="utf-8")
    media = tmp_path / "file1.mp4"
    fake_info = {"title": "File", "id": "file1"}
    auth_calls: list[tuple[str, str]] = []

    def _run(url, source_dir, **kwargs):  # noqa: ANN001
        cookies_file = str(kwargs.get("cookies_file") or "")
        browser = str(kwargs.get("cookies_from_browser") or "")
        auth_calls.append((cookies_file, browser))
        if not cookies_file:
            raise YouTubeDownloadError(
                "authentication_required",
                "YouTube requires authentication to access this video.",
                retryable=False,
                status=YouTubeDownloadStatus.AUTHENTICATION_REQUIRED,
            )
        media.write_bytes(b"cookie-file-bytes")
        return media, fake_info

    with (
        patch(
            "ingestion.youtube.get_settings",
            return_value=_settings(
                youtube_download_format=PROGRESSIVE_FORMAT,
                youtube_cookies_file=str(cookie),
                youtube_cookies_from_browser="firefox",
                youtube_auth_fallback=True,
            ),
        ),
        patch("ingestion.youtube._resolve_ffmpeg", return_value="/bin/ffmpeg"),
        patch("tools.youtube.urls.normalize_youtube_url", return_value="https://youtu.be/file1"),
        patch("tools.youtube.urls.extract_video_id", return_value="file1"),
        patch("ingestion.youtube._run_ytdlp", side_effect=_run),
    ):
        result = download_youtube("https://youtu.be/file1", dest_dir=tmp_path)

    assert result.ok is True
    assert any(path.endswith("cookies.txt") and browser == "" for path, browser in auth_calls)
    assert not any(browser == "firefox" for _, browser in auth_calls)


def test_cloud_ignores_browser_and_cookie_file(tmp_path: Path) -> None:
    cookie = tmp_path / "cookies.txt"
    cookie.write_text("# Netscape\n", encoding="utf-8")
    calls = {"n": 0}

    def _boom(url, source_dir, **kwargs):  # noqa: ANN001
        calls["n"] += 1
        assert not kwargs.get("cookies_file")
        assert not kwargs.get("cookies_from_browser")
        raise YouTubeDownloadError(
            "authentication_required",
            "YouTube requires authentication to access this video.",
            retryable=False,
            status=YouTubeDownloadStatus.AUTHENTICATION_REQUIRED,
        )

    with (
        patch(
            "ingestion.youtube.get_settings",
            return_value=_settings(
                youtube_download_format=PROGRESSIVE_FORMAT,
                youtube_cookies_file=str(cookie),
                youtube_cookies_from_browser="chrome",
                youtube_auth_fallback=True,
                is_streamlit_cloud=True,
            ),
        ),
        patch("ingestion.youtube._resolve_ffmpeg", return_value="/bin/ffmpeg"),
        patch("tools.youtube.urls.normalize_youtube_url", return_value="https://youtu.be/cloud1"),
        patch("tools.youtube.urls.extract_video_id", return_value="cloud1"),
        patch("ingestion.youtube._run_ytdlp", side_effect=_boom),
    ):
        result = download_youtube("https://youtu.be/cloud1", dest_dir=tmp_path)

    assert result.ok is False
    assert result.error is not None
    assert result.error.status == YouTubeDownloadStatus.AUTHENTICATION_REQUIRED
    assert "upload" in user_message_for_youtube_error(result.error).lower()
    assert calls["n"] >= 1


def test_resolve_auth_cloud_empty(tmp_path: Path) -> None:
    cookie = tmp_path / "c.txt"
    cookie.write_text("x", encoding="utf-8")
    file_path, browser = _resolve_local_youtube_auth(
        _settings(
            is_streamlit_cloud=True,
            youtube_cookies_file=str(cookie),
            youtube_cookies_from_browser="chrome",
        )
    )
    assert file_path == ""
    assert browser == ""


def test_resolve_auth_file_priority(tmp_path: Path) -> None:
    cookie = tmp_path / "c.txt"
    cookie.write_text("x", encoding="utf-8")
    file_path, browser = _resolve_local_youtube_auth(
        _settings(
            youtube_cookies_file=str(cookie),
            youtube_cookies_from_browser="edge",
        )
    )
    assert file_path.endswith("c.txt")
    assert browser == ""


def test_error_warrants_auth_retry() -> None:
    assert _error_warrants_auth_retry(
        YouTubeDownloadError(
            "authentication_required",
            "auth",
            status=YouTubeDownloadStatus.AUTHENTICATION_REQUIRED,
        )
    )
    assert _error_warrants_auth_retry(
        YouTubeDownloadError(
            "forbidden",
            "YouTube blocked automated access from this environment.",
            status=YouTubeDownloadStatus.FORBIDDEN,
        )
    )
    assert not _error_warrants_auth_retry(
        YouTubeDownloadError(
            "unavailable",
            "gone",
            status=YouTubeDownloadStatus.UNAVAILABLE,
        )
    )
