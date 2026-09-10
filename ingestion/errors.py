"""Structured YouTube / upload ingestion errors."""

from __future__ import annotations

from enum import Enum


class YouTubeDownloadStatus(str, Enum):
    SUCCESS = "success"
    UNAVAILABLE = "unavailable"
    RESTRICTED = "restricted"
    AUTHENTICATION_REQUIRED = "authentication_required"
    FORBIDDEN = "forbidden"
    NETWORK_ERROR = "network_error"
    EXTRACTOR_ERROR = "extractor_error"
    UNKNOWN = "unknown"


class YouTubeDownloadError(Exception):
    """Typed failure for yt-dlp download attempts (never fake success)."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        status: YouTubeDownloadStatus | None = None,
    ) -> None:
        self.code = str(code or YouTubeDownloadStatus.UNKNOWN.value)
        self.message = str(message or "YouTube download failed")
        self.retryable = bool(retryable)
        self.status = status or _status_from_code(self.code)
        super().__init__(self.message)

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "status": self.status.value,
        }


USER_FACING_YOUTUBE_FAILURE = (
    "YouTube video could not be downloaded.\n\n"
    "The video may be unavailable to the hosted server, restricted,\n"
    "region-limited, require authentication, or protected against automated access.\n\n"
    "Please use another authorized public video or upload the media file directly."
)

_STATUS_USER_MESSAGES: dict[YouTubeDownloadStatus, str] = {
    YouTubeDownloadStatus.FORBIDDEN: (
        "YouTube blocked automated access from this server (HTTP 403 / bot check).\n\n"
        "Upload the video file directly (MP4/MOV/etc.) to continue analysis."
    ),
    YouTubeDownloadStatus.RESTRICTED: (
        "This YouTube video is private, age-restricted, or region-limited "
        "for the hosted server.\n\n"
        "Upload the media file directly to continue."
    ),
    YouTubeDownloadStatus.AUTHENTICATION_REQUIRED: (
        "This YouTube video requires authentication that could not be "
        "completed automatically.\n\n"
        "You can upload the video directly and the same AI analysis pipeline "
        "will continue.\n\n"
        "No other workflow changes are required."
    ),
    YouTubeDownloadStatus.UNAVAILABLE: (
        "YouTube reports this video as unavailable or removed.\n\n"
        "Try another public URL or upload the media file directly."
    ),
    YouTubeDownloadStatus.NETWORK_ERROR: (
        "A temporary network error occurred while contacting YouTube.\n\n"
        "Retry shortly, or upload the media file directly."
    ),
    YouTubeDownloadStatus.EXTRACTOR_ERROR: (
        "YouTube media extraction failed (invalid URL, missing formats, "
        "or missing FFmpeg for stream merge).\n\n"
        "Upload the video file directly, or ensure FFmpeg / yt-dlp are installed."
    ),
    YouTubeDownloadStatus.UNKNOWN: (
        "YouTube media download failed for an unexpected reason.\n\n"
        "Upload the media file directly to continue analysis."
    ),
}


def user_message_for_youtube_error(
    error: YouTubeDownloadError | None,
    *,
    include_generic: bool = True,
) -> str:
    """Return status-specific UI text; optionally append the generic help blurb."""
    status = (
        error.status
        if isinstance(error, YouTubeDownloadError)
        else YouTubeDownloadStatus.UNKNOWN
    )
    specific = _STATUS_USER_MESSAGES.get(
        status, _STATUS_USER_MESSAGES[YouTubeDownloadStatus.UNKNOWN]
    )
    detail = ""
    if isinstance(error, YouTubeDownloadError) and error.message:
        detail = f"\n\nTechnical detail: {error.code}: {error.message}"
    if include_generic and status not in {
        YouTubeDownloadStatus.FORBIDDEN,
        YouTubeDownloadStatus.RESTRICTED,
        YouTubeDownloadStatus.AUTHENTICATION_REQUIRED,
        YouTubeDownloadStatus.UNAVAILABLE,
    }:
        return f"{specific}{detail}\n\n---\n{USER_FACING_YOUTUBE_FAILURE}"
    return f"{specific}{detail}"


def user_message_for_status(status: YouTubeDownloadStatus | str) -> str:
    """Map a status enum/string to a short user-facing explanation."""
    if isinstance(status, str):
        try:
            status = YouTubeDownloadStatus(status)
        except ValueError:
            status = YouTubeDownloadStatus.UNKNOWN
    return _STATUS_USER_MESSAGES.get(
        status, _STATUS_USER_MESSAGES[YouTubeDownloadStatus.UNKNOWN]
    )


def classify_ytdlp_error(exc: BaseException) -> YouTubeDownloadError:
    """Map yt-dlp / network exceptions into structured application errors."""
    text = str(exc or "")
    lower = text.lower()

    if "403" in text or "forbidden" in lower:
        return YouTubeDownloadError(
            YouTubeDownloadStatus.FORBIDDEN.value,
            "YouTube rejected the media request with HTTP 403.",
            retryable=False,
            status=YouTubeDownloadStatus.FORBIDDEN,
        )
    if "sign in" in lower or "login required" in lower or "authentication" in lower:
        return YouTubeDownloadError(
            YouTubeDownloadStatus.AUTHENTICATION_REQUIRED.value,
            "YouTube requires authentication to access this video.",
            retryable=False,
            status=YouTubeDownloadStatus.AUTHENTICATION_REQUIRED,
        )
    if "private video" in lower or "private" in lower and "video" in lower:
        return YouTubeDownloadError(
            YouTubeDownloadStatus.RESTRICTED.value,
            "This YouTube video is private.",
            retryable=False,
            status=YouTubeDownloadStatus.RESTRICTED,
        )
    if "age" in lower and ("restrict" in lower or "confirm" in lower):
        return YouTubeDownloadError(
            YouTubeDownloadStatus.RESTRICTED.value,
            "This YouTube video is age-restricted.",
            retryable=False,
            status=YouTubeDownloadStatus.RESTRICTED,
        )
    if (
        "not available in your country" in lower
        or "region" in lower
        or "geo" in lower
        or "blocked" in lower
    ):
        return YouTubeDownloadError(
            YouTubeDownloadStatus.RESTRICTED.value,
            "This YouTube video is region-restricted for the hosted server.",
            retryable=False,
            status=YouTubeDownloadStatus.RESTRICTED,
        )
    if "unavailable" in lower or "removed" in lower or "does not exist" in lower:
        return YouTubeDownloadError(
            YouTubeDownloadStatus.UNAVAILABLE.value,
            "YouTube reports this video as unavailable.",
            retryable=False,
            status=YouTubeDownloadStatus.UNAVAILABLE,
        )
    if "bot" in lower or "confirm you're not a bot" in lower or "http error 429" in lower:
        return YouTubeDownloadError(
            YouTubeDownloadStatus.FORBIDDEN.value,
            "YouTube blocked automated access from this environment.",
            retryable=False,
            status=YouTubeDownloadStatus.FORBIDDEN,
        )
    if any(
        token in lower
        for token in (
            "timed out",
            "timeout",
            "temporarily unavailable",
            "connection reset",
            "connection aborted",
            "name or service not known",
            "network is unreachable",
            "503",
            "502",
        )
    ):
        return YouTubeDownloadError(
            YouTubeDownloadStatus.NETWORK_ERROR.value,
            f"Temporary network failure while contacting YouTube: {text}",
            retryable=True,
            status=YouTubeDownloadStatus.NETWORK_ERROR,
        )
    if (
        "format is not available" in lower
        or "requested format" in lower
        or "no video formats" in lower
        or "unsupported url" in lower
        or "extractor" in lower
    ):
        return YouTubeDownloadError(
            YouTubeDownloadStatus.EXTRACTOR_ERROR.value,
            f"YouTube extractor failure: {text}",
            retryable=False,
            status=YouTubeDownloadStatus.EXTRACTOR_ERROR,
        )
    return YouTubeDownloadError(
        YouTubeDownloadStatus.UNKNOWN.value,
        f"YouTube media download failed: {text}",
        retryable=False,
        status=YouTubeDownloadStatus.UNKNOWN,
    )


def _status_from_code(code: str) -> YouTubeDownloadStatus:
    try:
        return YouTubeDownloadStatus(code)
    except ValueError:
        return YouTubeDownloadStatus.UNKNOWN


class UploadValidationError(Exception):
    """Raised when a direct upload fails validation."""

    def __init__(self, message: str) -> None:
        self.message = str(message)
        super().__init__(self.message)
