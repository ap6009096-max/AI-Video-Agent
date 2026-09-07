"""Agent implementations for the AI Video Agent."""

from agents.audio_analysis_agent import AudioAnalysisAgent
from agents.avatar_agent import AvatarAgent
from agents.base import BaseAgent, PlaceholderAgent
from agents.broll_agent import BRollAgent
from agents.caption_agent import CaptionAgent
from agents.country_agent import CountryAgent
from agents.cultural_adaptation_agent import CulturalAdaptationAgent
from agents.environment_agent import EnvironmentAgent
from agents.export_agent import ExportAgent
from agents.funny_moment_agent import FunnyMomentAgent
from agents.humor_localization_agent import HumorLocalizationAgent
from agents.input_agent import InputAgent, route_for_source
from agents.language_agent import LanguageAgent
from agents.local_video_ingest_agent import LocalVideoIngestAgent
from agents.moment_detection_agent import MomentDetectionAgent
from agents.music_agent import MusicAgent
from agents.platform_agent import PlatformAgent
from agents.podcast_agent import PodcastAgent
from agents.quality_agent import QualityAgent
from agents.regional_agent import RegionalAgent
from agents.reframe_agent import ReframeAgent
from agents.render_agent import RenderAgent
from agents.research_agent import ResearchAgent
from agents.supervisor_agent import SupervisorAgent
from agents.scene_detection_agent import SceneDetectionAgent
from agents.script_agent import ScriptAgent
from agents.smart_clip_agent import SmartClipAgent
from agents.speaker_analysis_agent import SpeakerAnalysisAgent
from agents.story_agent import StoryAgent
from agents.text_agent import TextAgent
from agents.thumbnail_agent import ThumbnailAgent
from agents.seo_agent import SeoAgent
from agents.trend_agent import TrendAgent
from agents.repurpose_agent import RepurposeAgent
from agents.calendar_agent import ContentCalendarAgent
from agents.brand_agent import BrandAgent
from agents.analytics_agent import AnalyticsAgent
from agents.image_agent import ImageAgent
from agents.storyboard_agent import StoryboardAgent
from agents.video_generation_agent import VideoGenerationAgent
from agents.director_agent import DirectorAgent
from agents.character_agent import CharacterAgent
from agents.camera_agent import CameraAgent
from agents.motion_graphics_agent import MotionGraphicsAgent
from agents.documentary_agent import DocumentaryAgent
from agents.transcript_agent import TranscriptAgent
from agents.video_understanding_agent import VideoUnderstandingAgent
from agents.video_type_agent import VideoTypeAgent
from agents.visual_style_agent import VisualStyleAgent
from agents.viral_moment_agent import ViralMomentAgent
from agents.voice_agent import VoiceAgent
from agents.youtube_agent import YouTubeAgent

__all__ = [
    "BaseAgent",
    "PlaceholderAgent",
    "AudioAnalysisAgent",
    "AvatarAgent",
    "BRollAgent",
    "CaptionAgent",
    "CountryAgent",
    "CulturalAdaptationAgent",
    "EnvironmentAgent",
    "ExportAgent",
    "FunnyMomentAgent",
    "HumorLocalizationAgent",
    "InputAgent",
    "LanguageAgent",
    "LocalVideoIngestAgent",
    "MomentDetectionAgent",
    "MusicAgent",
    "PlatformAgent",
    "PodcastAgent",
    "QualityAgent",
    "RegionalAgent",
    "ReframeAgent",
    "RenderAgent",
    "ResearchAgent",
    "SupervisorAgent",
    "SceneDetectionAgent",
    "ScriptAgent",
    "SmartClipAgent",
    "SpeakerAnalysisAgent",
    "StoryAgent",
    "TextAgent",
    "ThumbnailAgent",
    "SeoAgent",
    "TrendAgent",
    "RepurposeAgent",
    "ContentCalendarAgent",
    "BrandAgent",
    "AnalyticsAgent",
    "ImageAgent",
    "StoryboardAgent",
    "VideoGenerationAgent",
    "DirectorAgent",
    "CharacterAgent",
    "CameraAgent",
    "MotionGraphicsAgent",
    "DocumentaryAgent",
    "TranscriptAgent",
    "VideoUnderstandingAgent",
    "VideoTypeAgent",
    "VisualStyleAgent",
    "ViralMomentAgent",
    "VoiceAgent",
    "YouTubeAgent",
    "route_for_source",
]
