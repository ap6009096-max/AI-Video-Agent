"""Application-specific exception hierarchy."""

from __future__ import annotations


class VideoAgentError(Exception):
    """Base error for the AI Video Agent."""


class ConfigurationError(VideoAgentError):
    """Raised when configuration is missing or invalid."""


class WorkflowError(VideoAgentError):
    """Raised when a LangGraph workflow step fails."""


class StorageError(VideoAgentError):
    """Raised when local filesystem storage operations fail."""


class InputValidationError(VideoAgentError):
    """Raised when user input fails Input Agent validation."""


class YouTubeAgentError(VideoAgentError):
    """Raised when YouTube URL validation or metadata preparation fails."""


class TextAgentError(VideoAgentError):
    """Raised when Text/Script Agent processing fails."""


class TranscriptAgentError(VideoAgentError):
    """Raised when Whisper Transcript Agent processing fails."""


class VideoUnderstandingError(VideoAgentError):
    """Raised when Video Understanding Agent analysis fails."""


class SceneDetectionError(VideoAgentError):
    """Raised when Scene Detection Agent processing fails."""


class AudioAnalysisError(VideoAgentError):
    """Raised when Audio Analysis Agent processing fails."""


class SpeakerAnalysisError(VideoAgentError):
    """Raised when Speaker Analysis Agent processing fails."""


class MomentDetectionError(VideoAgentError):
    """Raised when Moment Detection Agent processing fails."""


class FunnyMomentError(VideoAgentError):
    """Raised when Funny Moment Agent processing fails."""


class ViralMomentError(VideoAgentError):
    """Raised when Viral Moment Agent processing fails."""


class SmartClipError(VideoAgentError):
    """Raised when Smart Clip Selection Agent processing fails."""


class PodcastAgentError(VideoAgentError):
    """Raised when Podcast Agent packaging fails."""


class ResearchAgentError(VideoAgentError):
    """Raised when Research Agent report building fails."""


class SupervisorAgentError(VideoAgentError):
    """Raised when Supervisor Agent crew orchestration fails."""


class StoryAgentError(VideoAgentError):
    """Raised when Story Agent generation fails."""


class GeminiGenerationError(StoryAgentError):
    """Base error for classified Gemini generation failures."""

    def __init__(
        self,
        message: str,
        *,
        model: str = "",
        classification: str = "unknown",
        attempted_models: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.model = model
        self.classification = classification
        self.attempted_models = list(attempted_models or [])


class GeminiQuotaExhaustedError(GeminiGenerationError):
    """Raised when configured Gemini models have exhausted daily quota."""


class GeminiTemporaryRateLimitError(GeminiGenerationError):
    """Raised when bounded retries cannot clear a temporary rate limit."""


class GeminiAuthenticationError(GeminiGenerationError):
    """Raised when Gemini authentication or permission is rejected."""


class GeminiModelUnavailableError(GeminiGenerationError):
    """Raised when Gemini rejects a configured model or request."""


class ScriptAgentError(VideoAgentError):
    """Raised when Script Agent generation fails."""


class CountryAgentError(VideoAgentError):
    """Raised when Country Agent localization resolution fails."""


class RegionalAgentError(VideoAgentError):
    """Raised when Regional Agent localization resolution fails."""


class LanguageAgentError(VideoAgentError):
    """Raised when Language Agent localization fails."""


class CulturalAdaptationError(VideoAgentError):
    """Raised when Cultural Adaptation Agent processing fails."""


class HumorLocalizationError(VideoAgentError):
    """Raised when Humor Localization Agent processing fails."""


class VideoTypeAgentError(VideoAgentError):
    """Raised when Video Type Agent preset resolution fails."""


class VisualStyleAgentError(VideoAgentError):
    """Raised when Visual Style Agent preset resolution fails."""


class EnvironmentAgentError(VideoAgentError):
    """Raised when Environment Agent preset resolution fails."""


class BRollAgentError(VideoAgentError):
    """Raised when B-Roll Agent planning fails."""


class VoiceAgentError(VideoAgentError):
    """Raised when Voice Agent planning fails."""


class MusicAgentError(VideoAgentError):
    """Raised when Music Agent planning fails."""


class AvatarAgentError(VideoAgentError):
    """Raised when Avatar Agent planning fails."""


class ThumbnailAgentError(VideoAgentError):
    """Raised when Thumbnail Agent planning fails."""


class SeoAgentError(VideoAgentError):
    """Raised when SEO / Metadata Agent planning fails."""


class TrendAgentError(VideoAgentError):
    """Raised when Trend Detection Agent planning fails."""


class RepurposeAgentError(VideoAgentError):
    """Raised when Content Repurposing Agent planning fails."""


class CalendarAgentError(VideoAgentError):
    """Raised when Content Calendar Agent planning fails."""


class BrandAgentError(VideoAgentError):
    """Raised when Brand Agent planning fails."""


class AnalyticsAgentError(VideoAgentError):
    """Raised when Analytics Prediction Agent planning fails."""


class ImageAgentError(VideoAgentError):
    """Raised when Image Generation Agent planning or asset write fails."""


class StoryboardAgentError(VideoAgentError):
    """Raised when Storyboard Agent planning fails."""


class VideoGenerationAgentError(VideoAgentError):
    """Raised when Video Generation Agent planning fails."""


class DirectorAgentError(VideoAgentError):
    """Raised when Director Agent planning fails."""


class CharacterAgentError(VideoAgentError):
    """Raised when Character Management Agent planning fails."""


class CameraAgentError(VideoAgentError):
    """Raised when Camera Planning Agent planning fails."""


class MotionGraphicsAgentError(VideoAgentError):
    """Raised when Motion Graphics Agent planning fails."""


class DocumentaryAgentError(VideoAgentError):
    """Raised when Documentary Agent planning fails."""


class CaptionAgentError(VideoAgentError):
    """Raised when Caption Agent planning or export fails."""


class ReframeAgentError(VideoAgentError):
    """Raised when Smart Reframe Agent planning or encoding fails."""


class PlatformAgentError(VideoAgentError):
    """Raised when Platform Agent optimization or export metadata fails."""


class RenderAgentError(VideoAgentError):
    """Raised when Render Agent composition fails."""


class QualityAgentError(VideoAgentError):
    """Raised when Quality Agent validation fails after correction attempts."""


class ExportAgentError(VideoAgentError):
    """Raised when Export Agent packaging fails."""
