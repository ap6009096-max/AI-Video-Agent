"""Tests for the LangGraph video generation workflow."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

from agents.audio_analysis_agent import AudioAnalysisAgent
from agents.funny_moment_agent import FunnyMomentAgent
from agents.language_agent import LanguageAgent
from agents.moment_detection_agent import MomentDetectionAgent
from agents.scene_detection_agent import SceneDetectionAgent
from agents.script_agent import ScriptAgent
from agents.podcast_agent import PodcastAgent
from agents.research_agent import ResearchAgent
from agents.supervisor_agent import SupervisorAgent
from agents.smart_clip_agent import SmartClipAgent
from agents.speaker_analysis_agent import SpeakerAnalysisAgent
from agents.story_agent import StoryAgent
from agents.text_agent import TextAgent
from agents.transcript_agent import TranscriptAgent
from agents.video_understanding_agent import VideoUnderstandingAgent
from agents.viral_moment_agent import ViralMomentAgent
from config.settings import get_settings
from graph.workflow import (
    ANALYTICS_NODE,
    AUDIO_ANALYSIS_NODE,
    AVATAR_NODE,
    BROLL_NODE,
    CAPTIONS_NODE,
    CALENDAR_NODE,
    BRAND_NODE,
    COUNTRY_NODE,
    CULTURAL_NODE,
    ENVIRONMENT_NODE,
    EXPORT_NODE,
    FUNNY_MOMENT_NODE,
    HUMOR_NODE,
    IMAGE_GENERATION_NODE,
    LANGUAGE_NODE,
    MOMENT_DETECTION_NODE,
    MUSIC_NODE,
    PLATFORM_NODE,
    PODCAST_NODE,
    QUALITY_NODE,
    RESEARCH_NODE,
    SUPERVISOR_NODE,
    REFRAME_NODE,
    REGIONAL_NODE,
    RENDER_NODE,
    SCENE_DETECTION_NODE,
    SCRIPT_NODE,
    SMART_CLIP_NODE,
    SPEAKER_ANALYSIS_NODE,
    STEP_NODE_NAMES,
    STORY_NODE,
    STORYBOARD_NODE,
    THUMBNAIL_NODE,
    TRANSCRIPT_NODE,
    UNDERSTANDING_NODE,
    CHARACTER_NODE,
    CAMERA_NODE,
    DIRECTOR_NODE,
    MOTION_GRAPHICS_NODE,
    DOCUMENTARY_NODE,
    VIDEO_GENERATION_NODE,
    VIDEO_TYPE_NODE,
    VISUAL_STYLE_NODE,
    VIRAL_MOMENT_NODE,
    VOICE_NODE,
    build_graph,
    build_video_graph,
    run_video_workflow,
    run_workflow,
)
from schemas.analysis import (
    AudioCharacteristics,
    SceneSegment,
    VideoProperties,
    VisualChange,
)
from schemas.audio_speakers import ConversationalStructure, ScoredSpan, SpeakerTurn
from schemas.base import JobStatus
from schemas.clips import ClipCandidate
from schemas.funny import FunnyMoment
from schemas.job import (
    FeatureFlags,
    PIPELINE_STEPS,
    ProgressStepStatus,
    SourceType,
    VideoJobConfig,
    VideoJobRequest,
)
from schemas.moments import DetectedMoment
from schemas.podcast import PodcastClip
from schemas.research import (
    ResearchClaim,
    ResearchOutlineSection,
    ResearchReport,
    ResearchSource,
    TopicAnalysis,
)
from schemas.supervisor import GeminiSupervisorDecision
from schemas.project import ProjectMetadata
from schemas.scenes import DetectedScene
from schemas.transcript import (
    GeminiHook,
    GeminiScriptAnalysis,
    TranscriptAgentResult,
    WhisperSegment,
    WhisperTranscript,
    WhisperWord,
)
from schemas.viral import ViralMoment, ViralScoreBreakdown
from schemas.story import (
    GeminiClipScript,
    GeminiClipStory,
    GeminiScriptsBatch,
    GeminiStoriesBatch,
)
from schemas.localization import GeminiLocalizedBatch, GeminiLocalizedClip
from tools.moments.viral_detect import DISCLAIMER
from tools.whisper.adapter import whisper_to_structured
from tools.youtube.oembed_provider import OEmbedYouTubeProvider


def _fake_script_analysis(cleaned_text, sentences, sections) -> GeminiScriptAnalysis:
    return GeminiScriptAnalysis(
        language="English",
        topics=["demo"],
        section_titles=[f"Section {i + 1}" for i in range(len(sections))],
        hooks=[GeminiHook(sentence_index=0, reason="opener", score=0.8)],
        important_statements=[],
        clip_boundaries=[],
    )


def _install_mock_text_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "graph.workflow.TextAgent",
        lambda: TextAgent(analyze_fn=_fake_script_analysis),
    )


def _install_passthrough_render_for_fake_media(monkeypatch: pytest.MonkeyPatch) -> None:
    """Allow full-graph tests with placeholder MP4 bytes (no real FFmpeg encode)."""
    from tools.media.validate_video import ValidationResult

    def _ok(path, **_kwargs):
        p = Path(path) if path else None
        if not p or not p.is_file() or p.stat().st_size <= 0:
            return ValidationResult(ok=False, path=str(p or ""), reason="missing")
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
            size_bytes=int(p.stat().st_size),
        )

    def _encode(src, dest, **_kwargs):
        out = Path(dest)
        out.parent.mkdir(parents=True, exist_ok=True)
        src_p = Path(src)
        out.write_bytes(src_p.read_bytes() if src_p.is_file() else b"enc")
        return out

    def _cut(media, dest, *, start: float, end: float):
        out = Path(dest)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(f"cut-{start}-{end}".encode())
        return out

    def _concat(segments, dest):
        out = Path(dest)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"joined")
        return out

    fake_probe = {
        "duration": 1.0,
        "width": 1080,
        "height": 1920,
        "fps": 30.0,
        "video_codec": "h264",
        "audio_codec": "aac",
        "audio_sample_rate": 48000,
        "has_audio": True,
        "has_video": True,
        "container": "mp4",
    }

    monkeypatch.setattr("agents.render_agent.validate_video", _ok)
    monkeypatch.setattr("tools.media.validate_video.validate_video", _ok)
    monkeypatch.setattr("tools.quality.checks.probe_media", lambda *_a, **_k: dict(fake_probe))
    monkeypatch.setattr(
        "tools.quality.checks._sample_frames", lambda *_a, **_k: (True, True, "ok")
    )
    monkeypatch.setattr("tools.quality.checks.encode_mp4", _encode)
    monkeypatch.setattr("agents.render_agent.encode_mp4", _encode)
    monkeypatch.setattr("agents.render_agent.cut_segment", _cut)
    monkeypatch.setattr("agents.render_agent.concat_segments", _concat)
    monkeypatch.setattr("agents.render_agent.normalize_loudness", lambda *a, **k: None)
    monkeypatch.setattr("agents.render_agent.resize", lambda *a, **k: None)
    monkeypatch.setattr("agents.render_agent.burn_subtitles", lambda *a, **k: None)
    monkeypatch.setattr("agents.render_agent.extract_thumbnail", lambda *a, **k: None)
    monkeypatch.setattr("agents.render_agent.resolve_ffmpeg_binary", lambda: "ffmpeg")
    # Also stub burn-in tool in case captions path imports it directly
    monkeypatch.setattr(
        "tools.captions.burnin.burn_subtitles",
        lambda *a, **k: None,
        raising=False,
    )


def _fake_transcribe(media_path):
    return {
        "language": "en",
        "text": "Hello from mock whisper",
        "model": "base",
        "segments": [
            WhisperSegment(
                id=0,
                start=0.0,
                end=1.0,
                text="Hello from mock whisper",
                words=[WhisperWord(word="Hello", start=0.0, end=0.3)],
                confidence=0.9,
            )
        ],
        "raw": {},
    }


def _install_mock_transcript_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "agents.transcript_agent.extract_wav_for_asr",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "graph.workflow.TranscriptAgent",
        lambda: TranscriptAgent(transcribe_fn=_fake_transcribe),
    )


def _install_mock_understanding_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep CI fast: mock OpenCV/FFmpeg probes inside understanding agent."""

    def _probe(_path):
        return VideoProperties(
            duration_seconds=5.0,
            fps=30.0,
            width=640,
            height=360,
            frame_count=150,
            video_codec="h264",
            audio_codec="aac",
        )

    def _scenes(_path, **_kwargs):
        return {
            "sampled_frames": [],
            "scenes": [SceneSegment(id=0, start=0.0, end=5.0, score=0.0)],
            "visual_changes": [VisualChange(time_seconds=1.0, score=0.4, kind="cut")],
            "object_cues": [],
            "frames_analyzed": 5,
            "effective_sample_fps": 1.0,
        }

    def _audio(_path):
        return AudioCharacteristics(has_audio=True, sample_rate=44100, channels=2)

    monkeypatch.setattr(
        "tools.quality.checks.probe_media",
        lambda _p: {
            "path": str(_p),
            "exists": True,
            "duration": 5.0,
            "width": 1280,
            "height": 720,
            "fps": 30.0,
            "video_codec": "h264",
            "audio_codec": "aac",
            "audio_sample_rate": 44100,
            "has_audio": True,
            "has_video": True,
            "container": "mp4",
        },
    )
    monkeypatch.setattr(
        "tools.quality.checks._sample_frames",
        lambda _p: (True, True, "ok=3 black=0 bad=0"),
    )

    monkeypatch.setattr(
        "graph.workflow.VideoUnderstandingAgent",
        lambda: VideoUnderstandingAgent(
            probe_fn=_probe,
            scenes_fn=_scenes,
            audio_fn=_audio,
        ),
    )



def _install_mock_scene_detection_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    def _detect(**_kwargs):
        return {
            "scenes": [
                DetectedScene(
                    id=0,
                    start=0.0,
                    end=5.0,
                    duration=5.0,
                    visual_change_score=0.4,
                    description="Hard cut (score=0.40)",
                    change_kinds=["cut"],
                )
            ],
            "duration": 5.0,
            "source_signals": {"visual": 1, "speaker": 0, "event": 0, "rescanned": 0},
            "notes": "",
        }

    monkeypatch.setattr(
        "graph.workflow.SceneDetectionAgent",
        lambda: SceneDetectionAgent(detect_fn=_detect),
    )


def _install_mock_audio_speaker_agents(monkeypatch: pytest.MonkeyPatch) -> None:
    def _audio(**_kwargs):
        return {
            "silence_spans": [],
            "pause_spans": [],
            "volume_events": [],
            "intensity_spans": [],
            "laughter_candidates": [],
            "excitement_candidates": [],
            "question_spans": [
                ScoredSpan(
                    start=0.0,
                    end=1.0,
                    score=0.6,
                    label="question",
                    evidence_tags=["clip_boundary"],
                )
            ],
            "reaction_spans": [],
            "summary_scores": {
                "silence_ratio": 0.0,
                "speech_intensity": 0.3,
                "volume_dynamics": 0.0,
                "laughter": 0.0,
                "excitement": 0.0,
                "pause_density": 0.0,
                "question_density": 0.5,
                "reaction_density": 0.0,
            },
            "notes": "",
        }

    def _speakers(**_kwargs):
        return {
            "turns": [
                SpeakerTurn(
                    id=0, start=0.0, end=5.0, text_excerpt="hello", change_score=0.0
                )
            ],
            "speaker_change_candidates": [],
            "conversational_structure": ConversationalStructure(),
            "summary_scores": {"speaker_change_rate": 0.0, "turn_count": 1.0},
            "notes": "Speaker-independent turn heuristics — not true diarization.",
        }

    monkeypatch.setattr(
        "graph.workflow.AudioAnalysisAgent",
        lambda: AudioAnalysisAgent(analyze_fn=_audio),
    )
    monkeypatch.setattr(
        "graph.workflow.SpeakerAnalysisAgent",
        lambda: SpeakerAnalysisAgent(analyze_fn=_speakers),
    )


def _install_mock_moment_detection_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    def _analyze(**_kwargs):
        return [
            DetectedMoment(
                category="important",
                start=0.0,
                end=2.0,
                title="Key point",
                reason="hook",
                score=0.8,
                transcript="Key point",
                evidence=["transcript:hook"],
            )
        ]

    monkeypatch.setattr(
        "graph.workflow.MomentDetectionAgent",
        lambda: MomentDetectionAgent(analyze_fn=_analyze),
    )


def _install_mock_funny_moment_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    def _detect(**_kwargs):
        return [
            FunnyMoment(
                id=0,
                start=0.0,
                end=2.0,
                humor_kinds=["joke"],
                humor_score=0.7,
                explanation="signals=transcript,timing",
                transcript="Why did the chicken",
                suggested_title="Chicken setup",
                evidence=["transcript:joke_setup@0.0"],
            )
        ]

    monkeypatch.setattr(
        "graph.workflow.FunnyMomentAgent",
        lambda: FunnyMomentAgent(detect_fn=_detect),
    )


def _install_mock_viral_moment_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    def _detect(**_kwargs):
        return [
            ViralMoment(
                id=0,
                start=0.0,
                end=3.0,
                scores=ViralScoreBreakdown(hook=0.8, emotion=0.7),
                final_score=0.55,
                rank=1,
                explanation=DISCLAIMER,
                transcript="Hook line",
                suggested_title="Hook line",
                evidence=["seed:hook"],
            )
        ]

    monkeypatch.setattr(
        "graph.workflow.ViralMomentAgent",
        lambda: ViralMomentAgent(detect_fn=_detect),
    )


def _install_mock_smart_clip_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    def _select(**_kwargs):
        return [
            ClipCandidate(
                id=0,
                start=0.0,
                end=15.0,
                duration=15.0,
                transcript="Selected clip transcript.",
                category="important",
                score=0.8,
                hook="Selected clip transcript",
                reason="snapped to sentence boundaries",
                title="Selected clip",
                evidence=["seed:moments"],
            )
        ]

    monkeypatch.setattr(
        "graph.workflow.SmartClipAgent",
        lambda: SmartClipAgent(select_fn=_select),
    )


def _install_mock_podcast_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    def _package(**_kwargs):
        return [
            PodcastClip(
                id=0,
                start=0.0,
                end=40.0,
                duration=40.0,
                kind="quote",
                platforms=["quotes", "shorts"],
                transcript="This changes everything.",
                title="Sharp claim",
                hook="This changes everything",
                reason="quote package",
                score=0.85,
                evidence=["seed:quote"],
            )
        ]

    monkeypatch.setattr(
        "graph.workflow.PodcastAgent",
        lambda: PodcastAgent(package_fn=_package),
    )


def _install_mock_research_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    def _build(**kwargs):
        if kwargs.get("skipped"):
            return ResearchReport(
                project_id=kwargs.get("project_id") or "x",
                provider="disabled",
                skipped=True,
                notes="skipped",
            )
        return ResearchReport(
            project_id=kwargs.get("project_id") or "x",
            topic="Sleep science",
            topic_analysis=TopicAnalysis(primary_topic="Sleep science"),
            sources=[
                ResearchSource(
                    id="src:user_script",
                    kind="user_script",
                    title="User script",
                    excerpt="Sleep is essential for memory.",
                )
            ],
            claims=[
                ResearchClaim(
                    id="claim:0",
                    text="Sleep is essential for memory.",
                    source_ids=["src:user_script"],
                    confidence=0.9,
                )
            ],
            outline=[
                ResearchOutlineSection(
                    id="outline:0",
                    title="Core",
                    summary="Sleep and memory",
                    claim_ids=["claim:0"],
                )
            ],
            summary="Sleep is essential for memory.",
            provider="test-research",
        )

    monkeypatch.setattr(
        "graph.workflow.ResearchAgent",
        lambda: ResearchAgent(build_fn=_build),
    )


def _install_mock_story_script_agents(monkeypatch: pytest.MonkeyPatch) -> None:
    def _stories(clip_blocks, **_kwargs) -> GeminiStoriesBatch:
        return GeminiStoriesBatch(
            stories=[
                GeminiClipStory(
                    clip_id=0,
                    hook="Hook from source",
                    context="Brief context",
                    value_event="Core value from clip",
                    payoff="Clear payoff",
                    cta="Follow for more",
                )
            ]
        )

    def _scripts(clip_blocks, **_kwargs) -> GeminiScriptsBatch:
        return GeminiScriptsBatch(
            scripts=[
                GeminiClipScript(
                    clip_id=0,
                    title="Selected Clip Title",
                    hook="Hook from source",
                    short_script="Hook from source. Brief context. Core value. Payoff. Follow.",
                    caption="Watch this clip.",
                    cta="Follow for more",
                    thumbnail_text="Must Watch",
                    keywords=["clip", "tips"],
                )
            ]
        )

    monkeypatch.setattr(
        "graph.workflow.StoryAgent",
        lambda: StoryAgent(generate_fn=_stories),
    )
    monkeypatch.setattr(
        "graph.workflow.ScriptAgent",
        lambda: ScriptAgent(generate_fn=_scripts),
    )


def _install_mock_language_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    def _localize(script_blocks, *, locale_block: str = "", **_kwargs) -> GeminiLocalizedBatch:
        return GeminiLocalizedBatch(
            scripts=[
                GeminiLocalizedClip(
                    clip_id=0,
                    title="Localized Title",
                    hook="Localized hook",
                    short_script="Localized short script.",
                    caption="Localized caption",
                    cta="Follow",
                    thumbnail_text="Watch",
                    keywords=["local"],
                    voice_direction="Neutral clear voice",
                )
            ]
        )

    monkeypatch.setattr(
        "graph.workflow.LanguageAgent",
        lambda: LanguageAgent(localize_fn=_localize),
    )


def _install_passthrough_transcript_for_youtube(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """YouTube metadata-only path: inject a successful stub TranscriptAgent result."""

    class _StubTranscriptAgent:
        def run(self, project, project_dir=None, source_metadata=None, **_):
            meta = (
                project
                if isinstance(project, ProjectMetadata)
                else ProjectMetadata.model_validate(project)
            )
            speech = WhisperTranscript(
                project_id=meta.project_id,
                source_type=meta.source_type,
                media_path="",
                language="en",
                segments=[
                    WhisperSegment(id=0, start=0.0, end=1.0, text="Stub youtube audio")
                ],
                text="Stub youtube audio",
                model="base",
            )
            structured = whisper_to_structured(speech)
            return TranscriptAgentResult(
                speech_transcript=speech,
                structured_transcript=structured,
                transcript_path=str(
                    Path(project_dir or ".") / "transcripts" / "transcript.json"
                ),
                messages=["[transcript] stubbed for youtube test"],
            )

    monkeypatch.setattr("graph.workflow.TranscriptAgent", _StubTranscriptAgent)


def _install_mock_youtube_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MagicMock(spec=httpx.Client)

    def _get(url: str, params=None, **_kwargs):
        response = MagicMock()
        response.status_code = 200
        if "oembed" in url:
            response.json.return_value = {
                "title": "Workflow Test Video",
                "author_name": "Workflow Channel",
                "type": "video",
            }
        else:
            response.json.return_value = {"items": []}
        return response

    client.get.side_effect = _get
    provider = OEmbedYouTubeProvider(client=client)
    monkeypatch.setattr(
        "agents.youtube_agent.get_youtube_provider",
        lambda: provider,
    )
    monkeypatch.setattr(
        "graph.workflow.YouTubeAgent",
        lambda: __import__("agents.youtube_agent", fromlist=["YouTubeAgent"]).YouTubeAgent(
            provider=provider
        ),
    )


def _install_mock_youtube_provider_with_media(
    monkeypatch: pytest.MonkeyPatch,
    media_file: Path,
) -> None:
    """Metadata plus an authorized local media file so the YouTube gate continues."""
    from schemas.youtube import PreparedYouTubeSource, YouTubeSourceStatus

    client = MagicMock(spec=httpx.Client)

    def _get(url: str, params=None, **_kwargs):
        response = MagicMock()
        response.status_code = 200
        if "oembed" in url:
            response.json.return_value = {
                "title": "Workflow Test Video",
                "author_name": "Workflow Channel",
                "type": "video",
            }
        else:
            response.json.return_value = {"items": []}
        return response

    client.get.side_effect = _get
    base = OEmbedYouTubeProvider(client=client)

    class _AuthorizedMediaProvider:
        name = "test_authorized"

        def normalize_url(self, url: str) -> str:
            return base.normalize_url(url)

        def fetch_metadata(self, url: str):
            return base.fetch_metadata(url)

        def prepare_source(self, project_dir, metadata):
            prepared = base.prepare_source(project_dir, metadata)
            media_file.parent.mkdir(parents=True, exist_ok=True)
            if not media_file.is_file():
                media_file.write_bytes(b"fake-yt-media")
            meta = prepared.metadata.model_copy(
                update={"source_status": YouTubeSourceStatus.READY_FOR_PIPELINE}
            )
            return PreparedYouTubeSource(
                source_dir=prepared.source_dir,
                metadata_path=prepared.metadata_path,
                local_media_path=str(media_file.resolve()),
                metadata=meta,
            )

    provider = _AuthorizedMediaProvider()
    monkeypatch.setattr(
        "agents.youtube_agent.get_youtube_provider",
        lambda: provider,
    )
    monkeypatch.setattr(
        "graph.workflow.YouTubeAgent",
        lambda: __import__("agents.youtube_agent", fromlist=["YouTubeAgent"]).YouTubeAgent(
            provider=provider
        ),
    )


def test_build_graph_compiles() -> None:
    assert build_graph() is not None
    assert build_video_graph() is not None


def test_step_node_count() -> None:
    assert len(PIPELINE_STEPS) == 15
    assert "input_agent" in STEP_NODE_NAMES
    assert "youtube_ingest" in STEP_NODE_NAMES
    assert "script_ingest" in STEP_NODE_NAMES
    assert TRANSCRIPT_NODE in STEP_NODE_NAMES
    assert UNDERSTANDING_NODE in STEP_NODE_NAMES
    assert SCENE_DETECTION_NODE in STEP_NODE_NAMES
    assert AUDIO_ANALYSIS_NODE in STEP_NODE_NAMES
    assert SPEAKER_ANALYSIS_NODE in STEP_NODE_NAMES
    assert FUNNY_MOMENT_NODE in STEP_NODE_NAMES
    assert VIRAL_MOMENT_NODE in STEP_NODE_NAMES
    assert MOMENT_DETECTION_NODE in STEP_NODE_NAMES
    assert SMART_CLIP_NODE in STEP_NODE_NAMES
    assert PODCAST_NODE in STEP_NODE_NAMES
    assert RESEARCH_NODE in STEP_NODE_NAMES
    assert SUPERVISOR_NODE in STEP_NODE_NAMES
    assert VIDEO_TYPE_NODE in STEP_NODE_NAMES
    assert VISUAL_STYLE_NODE in STEP_NODE_NAMES
    assert ENVIRONMENT_NODE in STEP_NODE_NAMES
    assert STORY_NODE in STEP_NODE_NAMES
    assert SCRIPT_NODE in STEP_NODE_NAMES
    assert COUNTRY_NODE in STEP_NODE_NAMES
    assert REGIONAL_NODE in STEP_NODE_NAMES
    assert CULTURAL_NODE in STEP_NODE_NAMES
    assert HUMOR_NODE in STEP_NODE_NAMES
    assert LANGUAGE_NODE in STEP_NODE_NAMES
    assert BROLL_NODE in STEP_NODE_NAMES
    assert VOICE_NODE in STEP_NODE_NAMES
    assert AVATAR_NODE in STEP_NODE_NAMES
    assert MUSIC_NODE in STEP_NODE_NAMES
    assert CAPTIONS_NODE in STEP_NODE_NAMES
    assert REFRAME_NODE in STEP_NODE_NAMES
    assert PLATFORM_NODE in STEP_NODE_NAMES
    assert RENDER_NODE in STEP_NODE_NAMES
    assert QUALITY_NODE in STEP_NODE_NAMES
    assert EXPORT_NODE in STEP_NODE_NAMES
    assert len(STEP_NODE_NAMES) >= 15
    # PROMPT 25: story/script before creative type/style/env; moments before funny/viral
    assert STEP_NODE_NAMES.index(MOMENT_DETECTION_NODE) < STEP_NODE_NAMES.index(
        FUNNY_MOMENT_NODE
    )
    assert STEP_NODE_NAMES.index(FUNNY_MOMENT_NODE) < STEP_NODE_NAMES.index(
        VIRAL_MOMENT_NODE
    )
    assert STEP_NODE_NAMES.index(VIRAL_MOMENT_NODE) < STEP_NODE_NAMES.index(
        SMART_CLIP_NODE
    )
    assert STEP_NODE_NAMES.index(SMART_CLIP_NODE) < STEP_NODE_NAMES.index(PODCAST_NODE)
    assert STEP_NODE_NAMES.index(PODCAST_NODE) < STEP_NODE_NAMES.index(RESEARCH_NODE)
    assert STEP_NODE_NAMES.index(RESEARCH_NODE) < STEP_NODE_NAMES.index(SUPERVISOR_NODE)
    assert STEP_NODE_NAMES.index(SUPERVISOR_NODE) < STEP_NODE_NAMES.index(STORY_NODE)
    assert STEP_NODE_NAMES.index(STORY_NODE) < STEP_NODE_NAMES.index(SCRIPT_NODE)
    assert STEP_NODE_NAMES.index(SCRIPT_NODE) < STEP_NODE_NAMES.index(COUNTRY_NODE)
    assert STEP_NODE_NAMES.index(COUNTRY_NODE) < STEP_NODE_NAMES.index(REGIONAL_NODE)
    assert STEP_NODE_NAMES.index(REGIONAL_NODE) < STEP_NODE_NAMES.index(LANGUAGE_NODE)
    assert STEP_NODE_NAMES.index(LANGUAGE_NODE) < STEP_NODE_NAMES.index(CULTURAL_NODE)
    assert STEP_NODE_NAMES.index(CULTURAL_NODE) < STEP_NODE_NAMES.index(HUMOR_NODE)
    assert STEP_NODE_NAMES.index(HUMOR_NODE) < STEP_NODE_NAMES.index(VIDEO_TYPE_NODE)
    assert STEP_NODE_NAMES.index(VIDEO_TYPE_NODE) < STEP_NODE_NAMES.index(
        VISUAL_STYLE_NODE
    )
    assert STEP_NODE_NAMES.index(VISUAL_STYLE_NODE) < STEP_NODE_NAMES.index(
        ENVIRONMENT_NODE
    )
    assert STEP_NODE_NAMES.index(ENVIRONMENT_NODE) < STEP_NODE_NAMES.index(
        STORYBOARD_NODE
    )
    assert STEP_NODE_NAMES.index(STORYBOARD_NODE) < STEP_NODE_NAMES.index(
        CHARACTER_NODE
    )
    assert STEP_NODE_NAMES.index(CHARACTER_NODE) < STEP_NODE_NAMES.index(
        CAMERA_NODE
    )
    assert STEP_NODE_NAMES.index(CAMERA_NODE) < STEP_NODE_NAMES.index(
        DIRECTOR_NODE
    )
    assert STEP_NODE_NAMES.index(DIRECTOR_NODE) < STEP_NODE_NAMES.index(
        MOTION_GRAPHICS_NODE
    )
    assert STEP_NODE_NAMES.index(MOTION_GRAPHICS_NODE) < STEP_NODE_NAMES.index(
        DOCUMENTARY_NODE
    )
    assert STEP_NODE_NAMES.index(DOCUMENTARY_NODE) < STEP_NODE_NAMES.index(
        VIDEO_GENERATION_NODE
    )
    assert STEP_NODE_NAMES.index(VIDEO_GENERATION_NODE) < STEP_NODE_NAMES.index(
        IMAGE_GENERATION_NODE
    )
    assert STEP_NODE_NAMES.index(IMAGE_GENERATION_NODE) < STEP_NODE_NAMES.index(
        BROLL_NODE
    )
    # broll → … → captions → smart_reframe → platform → render → quality → export
    assert STEP_NODE_NAMES.index(BROLL_NODE) < STEP_NODE_NAMES.index(VOICE_NODE)
    assert STEP_NODE_NAMES.index(VOICE_NODE) < STEP_NODE_NAMES.index(AVATAR_NODE)
    assert STEP_NODE_NAMES.index(AVATAR_NODE) < STEP_NODE_NAMES.index(MUSIC_NODE)
    assert STEP_NODE_NAMES.index(MUSIC_NODE) < STEP_NODE_NAMES.index(CAPTIONS_NODE)
    assert STEP_NODE_NAMES.index(CAPTIONS_NODE) < STEP_NODE_NAMES.index(REFRAME_NODE)
    assert STEP_NODE_NAMES.index(REFRAME_NODE) < STEP_NODE_NAMES.index(PLATFORM_NODE)
    assert STEP_NODE_NAMES.index(PLATFORM_NODE) < STEP_NODE_NAMES.index(THUMBNAIL_NODE)
    assert STEP_NODE_NAMES.index(BRAND_NODE) < STEP_NODE_NAMES.index(THUMBNAIL_NODE)
    assert STEP_NODE_NAMES.index(CALENDAR_NODE) < STEP_NODE_NAMES.index(THUMBNAIL_NODE)
    assert STEP_NODE_NAMES.index(THUMBNAIL_NODE) < STEP_NODE_NAMES.index(ANALYTICS_NODE)
    assert STEP_NODE_NAMES.index(ANALYTICS_NODE) < STEP_NODE_NAMES.index(RENDER_NODE)
    assert STEP_NODE_NAMES.index(RENDER_NODE) < STEP_NODE_NAMES.index(QUALITY_NODE)
    assert STEP_NODE_NAMES.index(QUALITY_NODE) < STEP_NODE_NAMES.index(EXPORT_NODE)
    # No stub step_* nodes remain
    assert not any(n.startswith("step_14_") for n in STEP_NODE_NAMES)
    assert not any(n.startswith("step_13_") for n in STEP_NODE_NAMES)
    assert not any(n.startswith("step_12_") for n in STEP_NODE_NAMES)
    assert not any(n.startswith("step_11_") for n in STEP_NODE_NAMES)
    assert not any(n.startswith("step_10_") for n in STEP_NODE_NAMES)
    assert not any(n.startswith("step_09_") for n in STEP_NODE_NAMES)
    assert not any(n.startswith("step_08_") for n in STEP_NODE_NAMES)


def test_run_video_workflow_completes_all_steps(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    _install_mock_text_agent(monkeypatch)
    _install_mock_story_script_agents(monkeypatch)
    _install_mock_language_agent(monkeypatch)

    request = VideoJobRequest(
        source_type=SourceType.SCRIPT,
        script_text="smoke-test script. Second sentence for structure.",
    )
    result = run_video_workflow(request)

    assert result["status"] == JobStatus.COMPLETED.value
    assert result["error"] is None
    assert result["result"] is not None
    assert result["project"] is not None
    assert result["project"]["source_type"] == SourceType.SCRIPT.value
    assert result["project_dir"] is not None
    assert Path(result["project_dir"]).is_dir()
    assert (Path(result["project_dir"]) / "project.json").is_file()
    assert result["next_agent"] == "script_ingest"
    assert result["transcript"] is not None
    assert (Path(result["project_dir"]) / "transcript.json").is_file()
    assert result["analysis"] is not None
    assert (Path(result["project_dir"]) / "analysis" / "video_analysis.json").is_file()
    assert result["scenes"] is not None
    assert (Path(result["project_dir"]) / "analysis" / "scenes.json").is_file()
    assert result["audio_analysis"] is not None
    assert (Path(result["project_dir"]) / "analysis" / "audio_analysis.json").is_file()
    assert result["speakers"] is not None
    assert (Path(result["project_dir"]) / "analysis" / "speakers.json").is_file()
    assert result["funny_moments"] is not None
    assert (Path(result["project_dir"]) / "analysis" / "funny_moments.json").is_file()
    assert result["viral_moments"] is not None
    assert (Path(result["project_dir"]) / "analysis" / "viral_moments.json").is_file()
    assert result["moments"] is not None
    assert (Path(result["project_dir"]) / "analysis" / "moments.json").is_file()
    assert result["clips"] is not None
    assert (Path(result["project_dir"]) / "analysis" / "clips.json").is_file()
    assert result["video_type_pack"] is not None
    assert (Path(result["project_dir"]) / "analysis" / "video_type.json").is_file()
    assert result["visual_style_pack"] is not None
    assert result["visual_style_pack"]["plan"]["summary"]
    assert (Path(result["project_dir"]) / "analysis" / "visual_style.json").is_file()
    assert result["environment_pack"] is not None
    assert result["environment_pack"]["plan"]["summary"]
    assert (Path(result["project_dir"]) / "analysis" / "environment.json").is_file()
    assert result["stories"] is not None
    assert (Path(result["project_dir"]) / "analysis" / "stories.json").is_file()
    assert result["scripts"] is not None
    assert (Path(result["project_dir"]) / "analysis" / "scripts.json").is_file()
    assert result["localizations"] is not None
    assert (Path(result["project_dir"]) / "analysis" / "localizations.json").is_file()
    assert (Path(result["project_dir"]) / "analysis" / "locale_context.json").is_file()
    assert result["cultural_adaptation"] is not None
    assert (Path(result["project_dir"]) / "analysis" / "cultural_adaptation.json").is_file()
    assert result["humor_localization"] is not None
    assert (Path(result["project_dir"]) / "analysis" / "humor_localization.json").is_file()
    assert result["broll_pack"] is not None
    assert (Path(result["project_dir"]) / "analysis" / "broll_plan.json").is_file()
    assert result["voice_pack"] is not None
    assert (Path(result["project_dir"]) / "analysis" / "voice_plan.json").is_file()
    assert result["music_pack"] is not None
    assert result["music_pack"]["plan"]["generation_required"] is False
    assert (Path(result["project_dir"]) / "analysis" / "music_plan.json").is_file()
    assert result["captions_pack"] is not None
    assert (Path(result["project_dir"]) / "analysis" / "captions_plan.json").is_file()
    assert result["reframe_pack"] is not None
    assert (Path(result["project_dir"]) / "analysis" / "reframe_plan.json").is_file()
    assert result["platform_pack"] is not None
    assert (Path(result["project_dir"]) / "analysis" / "platform_plan.json").is_file()
    assert (Path(result["project_dir"]) / "exports" / "platform_metadata.json").is_file()
    assert result["platform_pack"]["plan"]["export_hints"]["publish_status"] == (
        "not_published"
    )
    assert result["render_pack"] is not None
    assert (Path(result["project_dir"]) / "analysis" / "render_plan.json").is_file()
    assert result["quality_pack"] is not None
    assert (Path(result["project_dir"]) / "analysis" / "quality_report.json").is_file()
    assert result["export_pack"] is not None
    assert (Path(result["project_dir"]) / "exports" / "manifest.json").is_file()
    # Script path: honest soft-skip (no silent broken video)
    assert result["render_pack"]["plan"]["encoded"] is False
    assert result["quality_pack"]["report"]["skipped"] is True
    assert result["result"]["export_path"]
    assert result["result"]["export_pack"] is not None
    # PROMPT 25 dual-write aliases
    root = Path(result["project_dir"])
    assert (root / "localization.json").is_file()
    assert (root / "video_plan.json").is_file()
    assert (root / "subtitles").is_dir()
    assert (root / "final").is_dir()
    assert (root / "thumbnails").is_dir()
    assert result["result"].get("output_files") is not None

    steps = result["steps"]
    assert len(steps) == 15
    assert all(s["status"] == ProgressStepStatus.COMPLETED.value for s in steps)

    get_settings.cache_clear()


def test_run_workflow_compat_wrapper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    _install_mock_text_agent(monkeypatch)
    _install_mock_story_script_agents(monkeypatch)
    _install_mock_language_agent(monkeypatch)

    result = run_workflow("smoke-test. Another line.")
    assert result["status"] == JobStatus.COMPLETED.value
    assert result["job"]["source_type"] == SourceType.SCRIPT.value
    assert result["job"]["script_text"] == "smoke-test. Another line."
    assert result["project"] is not None
    assert result["transcript"] is not None
    assert result["analysis"] is not None
    assert result["scenes"] is not None
    assert result["audio_analysis"] is not None
    assert result["speakers"] is not None
    assert result["funny_moments"] is not None
    assert result["viral_moments"] is not None
    assert result["moments"] is not None
    assert result["clips"] is not None
    assert result["stories"] is not None
    assert result["scripts"] is not None
    assert result["localizations"] is not None
    assert result["cultural_adaptation"] is not None
    assert result["humor_localization"] is not None

    get_settings.cache_clear()


def test_on_step_callback_invoked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    _install_mock_transcript_agent(monkeypatch)
    _install_mock_understanding_agent(monkeypatch)
    _install_mock_scene_detection_agent(monkeypatch)
    _install_mock_audio_speaker_agents(monkeypatch)
    _install_mock_funny_moment_agent(monkeypatch)
    _install_mock_viral_moment_agent(monkeypatch)
    _install_mock_moment_detection_agent(monkeypatch)
    _install_mock_smart_clip_agent(monkeypatch)
    _install_mock_story_script_agents(monkeypatch)
    _install_mock_language_agent(monkeypatch)
    _install_passthrough_render_for_fake_media(monkeypatch)

    video = tmp_path / "callback.mp4"
    video.write_bytes(b"fake")

    seen: list[int] = []

    def _on_step(state: dict) -> None:
        seen.append(state.get("current_step", -1))

    request = VideoJobRequest(
        source_type=SourceType.UPLOAD,
        upload_path=str(video),
    )
    run_video_workflow(request, on_step=_on_step)
    assert len(seen) >= 15
    get_settings.cache_clear()


def test_youtube_workflow_gates_without_local_media(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Metadata-only YouTube must fail before Whisper, not crash mid-transcript."""
    from core.errors import WorkflowError

    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    _install_mock_youtube_provider(monkeypatch)

    request = VideoJobRequest(
        source_type=SourceType.YOUTUBE,
        youtube_url="https://www.youtube.com/watch?v=abcdefghijk",
    )
    with pytest.raises(WorkflowError, match="local media"):
        run_video_workflow(request)
    get_settings.cache_clear()


def test_youtube_workflow_continues_with_authorized_local_media(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    media = tmp_path / "authorized" / "youtube_video.mp4"
    _install_mock_youtube_provider_with_media(monkeypatch, media)
    _install_passthrough_transcript_for_youtube(monkeypatch)
    _install_mock_understanding_agent(monkeypatch)
    _install_mock_scene_detection_agent(monkeypatch)
    _install_mock_audio_speaker_agents(monkeypatch)
    _install_mock_funny_moment_agent(monkeypatch)
    _install_mock_viral_moment_agent(monkeypatch)
    _install_mock_moment_detection_agent(monkeypatch)
    _install_mock_smart_clip_agent(monkeypatch)
    _install_mock_story_script_agents(monkeypatch)
    _install_mock_language_agent(monkeypatch)
    _install_passthrough_render_for_fake_media(monkeypatch)

    request = VideoJobRequest(
        source_type=SourceType.YOUTUBE,
        youtube_url="https://www.youtube.com/watch?v=abcdefghijk",
    )
    result = run_video_workflow(request)
    assert result["next_agent"] == "youtube_ingest"
    assert result["source_metadata"] is not None
    assert result["source_metadata"]["local_media_path"]
    assert Path(result["source_metadata"]["local_media_path"]).is_file()
    assert result["project"].get("source_path")
    assert Path(result["project"]["source_path"]).is_file()
    assert result["status"] == JobStatus.COMPLETED.value
    assert result["speech_transcript"] is not None
    assert result["analysis"] is not None
    assert result["scenes"] is not None
    assert result["audio_analysis"] is not None
    assert result["speakers"] is not None
    assert result["funny_moments"] is not None
    assert result["viral_moments"] is not None
    assert result["moments"] is not None
    assert result["clips"] is not None
    assert result["stories"] is not None
    assert result["scripts"] is not None
    assert result["localizations"] is not None
    get_settings.cache_clear()


def test_youtube_workflow_download_enabled_uses_ytdlp_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With YOUTUBE_DOWNLOAD_ENABLED, mocked yt-dlp produces media and passes the gate."""
    from tools.youtube.ytdlp_provider import YtdlpYouTubeProvider

    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("YOUTUBE_DOWNLOAD_ENABLED", "true")
    get_settings.cache_clear()

    client = MagicMock(spec=httpx.Client)

    def _get(url: str, params=None, **_kwargs):
        response = MagicMock()
        response.status_code = 200
        if "oembed" in url:
            response.json.return_value = {
                "title": "Download Test Video",
                "author_name": "DL Channel",
                "type": "video",
            }
        else:
            response.json.return_value = {"items": []}
        return response

    client.get.side_effect = _get
    base = OEmbedYouTubeProvider(client=client)

    def _fake_download(url: str, source_dir: Path, options: dict) -> Path:
        out = source_dir / "youtube_video.mp4"
        out.write_bytes(b"downloaded")
        return out.resolve()

    provider = YtdlpYouTubeProvider(metadata_provider=base, download_fn=_fake_download)
    monkeypatch.setattr(
        "agents.youtube_agent.get_youtube_provider",
        lambda: provider,
    )
    monkeypatch.setattr(
        "graph.workflow.YouTubeAgent",
        lambda: __import__("agents.youtube_agent", fromlist=["YouTubeAgent"]).YouTubeAgent(
            provider=provider
        ),
    )
    _install_passthrough_transcript_for_youtube(monkeypatch)
    _install_mock_understanding_agent(monkeypatch)
    _install_mock_scene_detection_agent(monkeypatch)
    _install_mock_audio_speaker_agents(monkeypatch)
    _install_mock_funny_moment_agent(monkeypatch)
    _install_mock_viral_moment_agent(monkeypatch)
    _install_mock_moment_detection_agent(monkeypatch)
    _install_mock_smart_clip_agent(monkeypatch)
    _install_mock_story_script_agents(monkeypatch)
    _install_mock_language_agent(monkeypatch)
    _install_passthrough_render_for_fake_media(monkeypatch)

    result = run_video_workflow(
        VideoJobRequest(
            source_type=SourceType.YOUTUBE,
            youtube_url="https://www.youtube.com/watch?v=abcdefghijk",
        )
    )
    assert result["status"] == JobStatus.COMPLETED.value
    assert result["source_metadata"]["local_media_path"]
    assert Path(result["source_metadata"]["local_media_path"]).is_file()
    assert result["speech_transcript"] is not None
    get_settings.cache_clear()


def test_route_after_youtube_requires_local_file() -> None:
    from graph.workflow import _route_after_youtube

    assert (
        _route_after_youtube(
            {
                "status": JobStatus.RUNNING.value,
                "error": None,
                "project": {"source_path": ""},
                "source_metadata": {"local_media_path": None},
            }
        )
        == "youtube_failed"
    )
    assert (
        _route_after_youtube(
            {
                "status": JobStatus.FAILED.value,
                "error": "boom",
                "project": {},
                "source_metadata": {},
            }
        )
        == "youtube_failed"
    )


def test_route_after_local_video_requires_local_file(tmp_path: Path) -> None:
    from graph.workflow import _resolve_workflow_local_media, _route_after_local_video

    assert (
        _route_after_local_video(
            {
                "status": JobStatus.RUNNING.value,
                "error": None,
                "project": {"source_path": ""},
                "source_metadata": {
                    "local_media_path": None,
                    "media_path": None,
                    "local_path": None,
                },
            }
        )
        == "local_video_failed"
    )
    assert (
        _route_after_local_video(
            {
                "status": JobStatus.FAILED.value,
                "error": "copy failed",
                "project": {},
                "source_metadata": {},
            }
        )
        == "local_video_failed"
    )

    missing = tmp_path / "missing.mp4"
    assert (
        _route_after_local_video(
            {
                "status": JobStatus.RUNNING.value,
                "error": None,
                "project": {"source_path": str(missing)},
                "source_metadata": {"local_media_path": str(missing)},
            }
        )
        == "local_video_failed"
    )

    present = tmp_path / "present.mp4"
    present.write_bytes(b"ok")
    state = {
        "status": JobStatus.RUNNING.value,
        "error": None,
        "project": {"source_path": str(present)},
        "source_metadata": {
            "local_media_path": str(present),
            "media_path": str(present),
            "local_path": str(present),
        },
    }
    assert _resolve_workflow_local_media(state) == str(present)
    assert _route_after_local_video(state) == "continue"


def test_resolve_workflow_local_media_accepts_upload_keys(tmp_path: Path) -> None:
    from graph.workflow import _resolve_workflow_local_media

    media = tmp_path / "clip.mp4"
    media.write_bytes(b"x")
    # Only media_path (legacy upload key) should resolve.
    assert (
        _resolve_workflow_local_media(
            {
                "project": {},
                "source_metadata": {"media_path": str(media)},
            }
        )
        == str(media)
    )

def test_upload_workflow_runs_whisper_transcript(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    _install_mock_transcript_agent(monkeypatch)
    _install_mock_understanding_agent(monkeypatch)
    _install_mock_scene_detection_agent(monkeypatch)
    _install_mock_audio_speaker_agents(monkeypatch)
    _install_mock_funny_moment_agent(monkeypatch)
    _install_mock_viral_moment_agent(monkeypatch)
    _install_mock_moment_detection_agent(monkeypatch)
    _install_mock_smart_clip_agent(monkeypatch)
    _install_mock_story_script_agents(monkeypatch)
    _install_mock_language_agent(monkeypatch)
    _install_passthrough_render_for_fake_media(monkeypatch)

    video = tmp_path / "upload.mp4"
    video.write_bytes(b"fake")

    request = VideoJobRequest(
        job_id="upload-job-1",
        source_type=SourceType.UPLOAD,
        upload_path=str(video),
    )
    result = run_video_workflow(request)
    assert result["status"] == JobStatus.COMPLETED.value
    assert result["source_metadata"] is not None
    assert result["source_metadata"].get("local_media_path")
    assert Path(result["source_metadata"]["local_media_path"]).is_file()
    assert result["project"].get("source_path")
    assert Path(result["project"]["source_path"]).is_file()
    assert result["project"]["source_path"] == result["source_metadata"]["local_media_path"]
    assert result["speech_transcript"] is not None
    assert result["speech_transcript"]["language"] == "en"
    assert result["transcript"] is not None
    speech_path = Path(result["project_dir"]) / "transcripts" / "transcript.json"
    assert speech_path.is_file()
    assert result["analysis"] is not None
    assert result["analysis"]["properties"]["duration_seconds"] == 5.0
    assert (Path(result["project_dir"]) / "analysis" / "video_analysis.json").is_file()
    assert result["scenes"] is not None
    assert result["scenes"]["scenes"][0]["duration"] == 5.0
    assert (Path(result["project_dir"]) / "analysis" / "scenes.json").is_file()
    assert result["audio_analysis"] is not None
    assert result["audio_analysis"]["summary_scores"]["question_density"] == 0.5
    assert (Path(result["project_dir"]) / "analysis" / "audio_analysis.json").is_file()
    assert result["speakers"] is not None
    assert result["speakers"]["turns"]
    assert (Path(result["project_dir"]) / "analysis" / "speakers.json").is_file()
    assert result["funny_moments"] is not None
    assert (Path(result["project_dir"]) / "analysis" / "funny_moments.json").is_file()
    assert result["viral_moments"] is not None
    assert (Path(result["project_dir"]) / "analysis" / "viral_moments.json").is_file()
    assert result["moments"] is not None
    assert result["moments"]["moments"][0]["category"] == "important"
    assert (Path(result["project_dir"]) / "analysis" / "moments.json").is_file()
    assert result["clips"] is not None
    assert result["clips"]["clips"][0]["hook"]
    assert (Path(result["project_dir"]) / "analysis" / "clips.json").is_file()
    assert result["podcast_clips"] is not None
    assert (Path(result["project_dir"]) / "analysis" / "podcast_clips.json").is_file()
    assert result["research_report"] is not None
    assert (Path(result["project_dir"]) / "analysis" / "research_report.json").is_file()
    assert result["video_type_pack"] is not None
    assert result["video_type_pack"]["preset"]["name"]
    assert (Path(result["project_dir"]) / "analysis" / "video_type.json").is_file()
    assert result["visual_style_pack"] is not None
    assert result["visual_style_pack"]["plan"]["summary"]
    assert (Path(result["project_dir"]) / "analysis" / "visual_style.json").is_file()
    assert result["environment_pack"] is not None
    assert result["environment_pack"]["plan"]["summary"]
    assert (Path(result["project_dir"]) / "analysis" / "environment.json").is_file()
    assert result["stories"] is not None
    assert result["stories"]["stories"][0]["structure"]["hook"]
    assert (Path(result["project_dir"]) / "analysis" / "stories.json").is_file()
    assert result["scripts"] is not None
    assert result["scripts"]["scripts"][0]["title"]
    assert (Path(result["project_dir"]) / "analysis" / "scripts.json").is_file()
    assert result["localizations"] is not None
    assert result["localizations"]["versions"]
    assert (Path(result["project_dir"]) / "analysis" / "localizations.json").is_file()
    assert result["cultural_adaptation"] is not None
    assert result["humor_localization"] is not None
    assert (Path(result["project_dir"]) / "analysis" / "cultural_adaptation.json").is_file()
    assert (Path(result["project_dir"]) / "analysis" / "humor_localization.json").is_file()
    assert result["broll_pack"] is not None
    assert (Path(result["project_dir"]) / "analysis" / "broll_plan.json").is_file()
    assert result["voice_pack"] is not None
    assert (Path(result["project_dir"]) / "analysis" / "voice_plan.json").is_file()
    assert result["music_pack"] is not None
    assert result["music_pack"]["plan"]["generation_required"] is False
    assert (Path(result["project_dir"]) / "analysis" / "music_plan.json").is_file()
    assert result["captions_pack"] is not None
    assert (Path(result["project_dir"]) / "analysis" / "captions_plan.json").is_file()
    assert result["reframe_pack"] is not None
    assert (Path(result["project_dir"]) / "analysis" / "reframe_plan.json").is_file()
    assert result["platform_pack"] is not None
    assert (Path(result["project_dir"]) / "analysis" / "platform_plan.json").is_file()
    assert (Path(result["project_dir"]) / "exports" / "platform_metadata.json").is_file()
    assert result["render_pack"] is not None
    assert (Path(result["project_dir"]) / "analysis" / "render_plan.json").is_file()
    assert result["quality_pack"] is not None
    assert (Path(result["project_dir"]) / "analysis" / "quality_report.json").is_file()
    assert result["export_pack"] is not None
    assert (Path(result["project_dir"]) / "exports" / "manifest.json").is_file()
    get_settings.cache_clear()


def test_podcast_video_type_writes_podcast_clips(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    _install_mock_transcript_agent(monkeypatch)
    _install_mock_understanding_agent(monkeypatch)
    _install_mock_scene_detection_agent(monkeypatch)
    _install_mock_audio_speaker_agents(monkeypatch)
    _install_mock_funny_moment_agent(monkeypatch)
    _install_mock_viral_moment_agent(monkeypatch)
    _install_mock_moment_detection_agent(monkeypatch)
    _install_mock_smart_clip_agent(monkeypatch)
    _install_mock_podcast_agent(monkeypatch)
    _install_mock_story_script_agents(monkeypatch)
    _install_mock_language_agent(monkeypatch)
    _install_passthrough_render_for_fake_media(monkeypatch)

    video = tmp_path / "podcast.mp4"
    video.write_bytes(b"fake")

    request = VideoJobRequest(
        job_id="podcast-job-1",
        source_type=SourceType.UPLOAD,
        upload_path=str(video),
        config=VideoJobConfig(video_type="Podcast"),
        features=FeatureFlags(podcast_clips=False),
    )
    result = run_video_workflow(request)
    assert result["status"] == JobStatus.COMPLETED.value
    assert result["podcast_clips"] is not None
    assert result["podcast_clips"]["clips"]
    assert result["podcast_clips"]["clips"][0]["kind"] == "quote"
    assert "shorts" in result["podcast_clips"]["clips"][0]["platforms"]
    assert (Path(result["project_dir"]) / "analysis" / "podcast_clips.json").is_file()
    get_settings.cache_clear()


def test_script_job_writes_research_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    _install_mock_text_agent(monkeypatch)
    _install_mock_research_agent(monkeypatch)
    _install_mock_story_script_agents(monkeypatch)
    _install_mock_language_agent(monkeypatch)

    request = VideoJobRequest(
        job_id="research-script-1",
        source_type=SourceType.SCRIPT,
        script_text="Sleep is essential for memory consolidation and recovery.",
        features=FeatureFlags(research=False),
    )
    result = run_video_workflow(request)
    assert result["status"] == JobStatus.COMPLETED.value
    assert result["research_report"] is not None
    assert result["research_report"]["skipped"] is False
    assert result["research_report"]["claims"]
    assert result["research_report"]["claims"][0]["source_ids"]
    assert (Path(result["project_dir"]) / "analysis" / "research_report.json").is_file()
    get_settings.cache_clear()


def test_supervisor_crew_writes_crew_json_and_finishes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Immediate FINISH still writes crew artifact (smoke)."""
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    _install_mock_text_agent(monkeypatch)
    _install_mock_research_agent(monkeypatch)
    _install_mock_story_script_agents(monkeypatch)
    _install_mock_language_agent(monkeypatch)

    monkeypatch.setattr(
        "graph.supervisor_crew.SupervisorAgent",
        lambda: SupervisorAgent(
            decide_fn=lambda **_k: GeminiSupervisorDecision(
                next_agent="FINISH",
                task="complete",
                reason="test finish",
                done=True,
            )
        ),
    )

    request = VideoJobRequest(
        job_id="crew-job-1",
        source_type=SourceType.SCRIPT,
        script_text="Sleep is essential for memory consolidation and recovery.",
        features=FeatureFlags(supervisor_crew=True, research=True),
    )
    result = run_video_workflow(request)
    assert result["status"] == JobStatus.COMPLETED.value
    assert result["supervisor_crew"] is not None
    assert result["supervisor_crew"]["finished"] is True
    assert result["delegation_log"] is not None
    assert (Path(result["project_dir"]) / "analysis" / "supervisor_crew.json").is_file()
    get_settings.cache_clear()


def test_supervisor_crew_delegates_story_then_script(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Full crew loop: story → script → FINISH with packs and task board."""
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    _install_mock_text_agent(monkeypatch)
    _install_mock_research_agent(monkeypatch)
    _install_mock_story_script_agents(monkeypatch)
    _install_mock_language_agent(monkeypatch)

    decide_seq = iter(["story", "script", "FINISH"])

    def _decide(**_kwargs):
        nxt = next(decide_seq, "FINISH")
        return GeminiSupervisorDecision(
            next_agent=nxt,
            task=f"Produce {nxt}" if nxt != "FINISH" else "complete",
            reason="stateful test sequence",
            done=nxt == "FINISH",
        )

    monkeypatch.setattr(
        "graph.supervisor_crew.SupervisorAgent",
        lambda: SupervisorAgent(decide_fn=_decide),
    )

    class _FakeCrewStory:
        def run(self, project, **kwargs):
            from schemas.story import (
                ClipStory,
                StoriesReport,
                StoryAgentResult,
                StoryStructure,
            )

            pid = getattr(project, "project_id", None) or project.get("project_id")
            root = Path(kwargs.get("project_dir") or ".")
            report = StoriesReport(
                project_id=pid,
                stories=[
                    ClipStory(
                        clip_id=0,
                        start=0.0,
                        end=10.0,
                        structure=StoryStructure(
                            hook="Hook line",
                            context="Context",
                            value_event="Value",
                            payoff="Payoff",
                            cta="Follow",
                        ),
                        source_excerpt="Sleep is essential.",
                    )
                ],
                provider="crew-test",
                notes="crew story mock",
            )
            path = root / "analysis" / "stories.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
            return StoryAgentResult(
                stories=report,
                stories_path=str(path),
                messages=["[story] crew mock ok"],
            )

    class _FakeCrewScript:
        def run(self, project, **kwargs):
            from schemas.story import (
                ClipScript,
                ScriptsReport,
                ScriptAgentResult,
                StoryStructure,
            )

            pid = getattr(project, "project_id", None) or project.get("project_id")
            root = Path(kwargs.get("project_dir") or ".")
            report = ScriptsReport(
                project_id=pid,
                scripts=[
                    ClipScript(
                        clip_id=0,
                        title="Sleep tips",
                        hook="Hook line",
                        short_script="Sleep is essential for memory.",
                        caption="Sleep matters.",
                        cta="Follow",
                        thumbnail_text="Sleep tips",
                        keywords=["sleep", "memory"],
                        story_structure=StoryStructure(hook="Hook line"),
                    )
                ],
                provider="crew-test",
                notes="crew script mock",
            )
            path = root / "analysis" / "scripts.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
            return ScriptAgentResult(
                scripts=report,
                scripts_path=str(path),
                messages=["[script] crew mock ok"],
            )

    monkeypatch.setattr("graph.supervisor_crew.StoryAgent", lambda: _FakeCrewStory())
    monkeypatch.setattr("graph.supervisor_crew.ScriptAgent", lambda: _FakeCrewScript())

    request = VideoJobRequest(
        job_id="crew-job-loop-1",
        source_type=SourceType.SCRIPT,
        script_text="Sleep is essential for memory consolidation and recovery.",
        features=FeatureFlags(supervisor_crew=True, research=True),
    )
    result = run_video_workflow(request)
    assert result["status"] == JobStatus.COMPLETED.value

    crew = result["supervisor_crew"]
    assert crew is not None
    assert crew["finished"] is True
    assert (Path(result["project_dir"]) / "analysis" / "supervisor_crew.json").is_file()

    log = result.get("delegation_log") or crew.get("delegation_log") or []
    assert log
    targets = {e.get("to_agent") for e in log}
    sources = {e.get("from_agent") for e in log}
    assert "story" in targets or "story" in sources
    assert "script" in targets or "script" in sources
    assert "supervisor" in sources

    board = result.get("task_board") or crew.get("task_board") or []
    done_assignees = {
        t.get("assignee") for t in board if t.get("status") == "done"
    }
    assert "story" in done_assignees
    assert "script" in done_assignees

    assert result["stories"] is not None
    assert result["stories"]["stories"]
    assert result["stories"]["stories"][0]["structure"]["hook"] == "Hook line"
    assert result["scripts"] is not None
    assert result["scripts"]["scripts"]
    assert result["scripts"]["scripts"][0]["title"] == "Sleep tips"

    messages = result.get("messages") or []
    assert any("supervisor → story" in m for m in messages)
    assert any("story → supervisor" in m for m in messages)
    assert any("supervisor → script" in m for m in messages)
    assert any("script → supervisor" in m for m in messages)
    get_settings.cache_clear()


def test_content_calendar_writes_plan_when_flag_on(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    get_settings.cache_clear()
    _install_mock_text_agent(monkeypatch)
    _install_mock_research_agent(monkeypatch)
    _install_mock_story_script_agents(monkeypatch)
    _install_mock_language_agent(monkeypatch)

    request = VideoJobRequest(
        job_id="calendar-job-1",
        source_type=SourceType.SCRIPT,
        script_text="Weekly habits for better focus and deep work.",
        config=VideoJobConfig(platform="YouTube", video_type="Shorts"),
        features=FeatureFlags(content_calendar=True, research=False),
    )
    result = run_video_workflow(request)
    assert result["status"] == JobStatus.COMPLETED.value
    assert result["calendar_pack"] is not None
    plan = result["calendar_pack"].get("plan") or {}
    assert plan.get("skipped") is False
    entries = plan.get("entries") or []
    assert entries
    assert set(entries[0].keys()) >= {"date", "topic", "platform", "video_type"}
    assert plan.get("daily") is not None
    assert plan.get("weekly") is not None
    assert plan.get("monthly") is not None
    path = Path(result["project_dir"]) / "analysis" / "calendar_plan.json"
    assert path.is_file()
    get_settings.cache_clear()


def test_brand_writes_plan_when_flag_on(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    get_settings.cache_clear()
    _install_mock_text_agent(monkeypatch)
    _install_mock_research_agent(monkeypatch)
    _install_mock_story_script_agents(monkeypatch)
    _install_mock_language_agent(monkeypatch)

    request = VideoJobRequest(
        job_id="brand-job-1",
        source_type=SourceType.SCRIPT,
        script_text="Brand-consistent tips for clear product storytelling.",
        config=VideoJobConfig(
            platform="YouTube",
            brand_preset="Corporate Clean",
            brand_name="Acme Labs",
        ),
        features=FeatureFlags(brand=True, research=False),
    )
    result = run_video_workflow(request)
    assert result["status"] == JobStatus.COMPLETED.value
    assert result["brand_pack"] is not None
    plan = result["brand_pack"].get("plan") or {}
    assert plan.get("skipped") is False
    assert plan.get("brand_name") == "Acme Labs"
    assert (plan.get("voice") or {}).get("tone")
    assert (plan.get("colors") or {}).get("primary")
    assert (plan.get("cta") or {}).get("style")
    assert (plan.get("messaging") or {}).get("tagline")
    path = Path(result["project_dir"]) / "analysis" / "brand_plan.json"
    assert path.is_file()
    get_settings.cache_clear()
