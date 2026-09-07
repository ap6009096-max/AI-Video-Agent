"""Video Understanding Agent — OpenCV/FFmpeg + transcript fusion."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from agents.base import BaseAgent
from config.settings import get_settings
from core.errors import StorageError, VideoUnderstandingError
from core.logging import get_logger
from core.paths import ensure_project_analysis_dir, ensure_project_dir, get_video_analysis_path
from schemas.analysis import (
    AudioCharacteristics,
    SpeakerPresence,
    TimeRange,
    VideoAnalysisReport,
    VideoProperties,
    VideoUnderstandingResult,
)
from schemas.project import ProjectMetadata

logger = get_logger(__name__)

ProbeFn = Callable[[str | Path], VideoProperties]
ScenesFn = Callable[..., dict[str, Any]]
AudioFn = Callable[[str | Path], AudioCharacteristics]


class VideoUnderstandingAgent(BaseAgent):
    """Analyze video/audio with sampled OpenCV/FFmpeg and transcript cues."""

    name = "video_understanding"

    def __init__(
        self,
        probe_fn: ProbeFn | None = None,
        scenes_fn: ScenesFn | None = None,
        audio_fn: AudioFn | None = None,
    ) -> None:
        self._probe_fn = probe_fn
        self._scenes_fn = scenes_fn
        self._audio_fn = audio_fn

    def run(
        self,
        project: ProjectMetadata | dict[str, Any],
        *,
        project_dir: str | Path | None = None,
        source_metadata: dict[str, Any] | None = None,
        speech_transcript: dict[str, Any] | None = None,
        transcript: dict[str, Any] | None = None,
        **_: Any,
    ) -> VideoUnderstandingResult:
        meta = self._coerce_project(project)
        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)

        media_path = self._resolve_media_path(meta, source_metadata)
        settings = get_settings()
        speaker = self._speaker_presence(speech_transcript, transcript, duration_hint=None)

        if not media_path:
            report = VideoAnalysisReport(
                project_id=project_id,
                media_path="",
                sample_fps=settings.analysis_sample_fps,
                frames_analyzed=0,
                properties=VideoProperties(),
                audio=AudioCharacteristics(
                    has_audio=False,
                    speech_ratio=speaker.estimated_speech_coverage or None,
                ),
                speaker_presence=speaker,
                notes=(
                    "Transcript-only analysis: no local video file available. "
                    "Visual/OpenCV/FFmpeg probing skipped."
                ),
                provider="transcript-only",
            )
            path = self._write_report(project_id, root, report)
            messages = [
                f"[{self.name}] Transcript-only mode (no local media)",
                f"[{self.name}] Speech coverage: {speaker.estimated_speech_coverage:.2f}",
                f"[{self.name}] Wrote analysis/video_analysis.json",
            ]
            return VideoUnderstandingResult(
                analysis=report, analysis_path=str(path), messages=messages
            )

        media = Path(media_path)
        try:
            from tools.audio.ffmpeg_probe import probe_audio_characteristics
            from tools.video.probe import probe_video_properties
            from tools.video.scenes import analyze_scenes

            probe = self._probe_fn or probe_video_properties
            scenes = self._scenes_fn or analyze_scenes
            audio_probe = self._audio_fn or probe_audio_characteristics

            props = probe(media)
            speaker = self._speaker_presence(
                speech_transcript,
                transcript,
                duration_hint=props.duration_seconds,
            )
            scene_result = scenes(
                media,
                sample_fps=settings.analysis_sample_fps,
                scene_threshold=settings.analysis_scene_threshold,
                max_frames=settings.analysis_max_frames,
            )
            audio = audio_probe(media)
            audio.speech_ratio = speaker.estimated_speech_coverage
        except VideoUnderstandingError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise VideoUnderstandingError(f"Video understanding failed: {exc}") from exc

        report = VideoAnalysisReport(
            project_id=project_id,
            media_path=str(media.resolve()),
            sample_fps=float(scene_result.get("effective_sample_fps") or settings.analysis_sample_fps),
            frames_analyzed=int(scene_result.get("frames_analyzed") or 0),
            properties=props,
            sampled_frames=list(scene_result.get("sampled_frames") or []),
            scenes=list(scene_result.get("scenes") or []),
            visual_changes=list(scene_result.get("visual_changes") or []),
            audio=audio,
            speaker_presence=speaker,
            object_cues=list(scene_result.get("object_cues") or []),
            notes="Sampled-frame analysis (not every frame).",
            provider="opencv-ffmpeg",
        )
        path = self._write_report(project_id, root, report)
        messages = [
            f"[{self.name}] Media: {media.name}",
            (
                f"[{self.name}] {props.width}x{props.height} @ {props.fps:.2f}fps, "
                f"duration={props.duration_seconds:.2f}s"
            ),
            f"[{self.name}] Frames analyzed: {report.frames_analyzed}",
            f"[{self.name}] Scenes: {len(report.scenes)}, visual changes: {len(report.visual_changes)}",
            f"[{self.name}] Audio: has_audio={audio.has_audio}",
            f"[{self.name}] Wrote analysis/video_analysis.json",
        ]
        logger.info(
            "VideoUnderstanding ready project_id=%s frames=%s scenes=%s",
            project_id,
            report.frames_analyzed,
            len(report.scenes),
        )
        return VideoUnderstandingResult(
            analysis=report, analysis_path=str(path), messages=messages
        )

    def _coerce_project(self, project: ProjectMetadata | dict[str, Any]) -> ProjectMetadata:
        if isinstance(project, ProjectMetadata):
            return project
        try:
            return ProjectMetadata.model_validate(project)
        except Exception as exc:  # noqa: BLE001
            raise VideoUnderstandingError(f"Invalid project metadata: {exc}") from exc

    def _resolve_media_path(
        self,
        meta: ProjectMetadata,
        source_metadata: dict[str, Any] | None,
    ) -> str | None:
        candidates: list[str] = []
        if meta.source_path:
            candidates.append(meta.source_path)
        if source_metadata and source_metadata.get("local_media_path"):
            candidates.append(str(source_metadata["local_media_path"]))
        for path in candidates:
            if path and Path(path).is_file():
                return path
        return None

    def _speaker_presence(
        self,
        speech_transcript: dict[str, Any] | None,
        transcript: dict[str, Any] | None,
        duration_hint: float | None,
    ) -> SpeakerPresence:
        ranges: list[TimeRange] = []
        if speech_transcript:
            for seg in speech_transcript.get("segments") or []:
                try:
                    start = float(seg.get("start", 0.0))
                    end = float(seg.get("end", start))
                except (TypeError, ValueError):
                    continue
                if end > start:
                    ranges.append(TimeRange(start=start, end=end))
        elif transcript:
            for sent in transcript.get("sentences") or []:
                start = sent.get("start_seconds")
                end = sent.get("end_seconds")
                if start is None or end is None:
                    continue
                try:
                    s = float(start)
                    e = float(end)
                except (TypeError, ValueError):
                    continue
                if e > s:
                    ranges.append(TimeRange(start=s, end=e))

        speech_dur = sum(max(0.0, r.end - r.start) for r in ranges)
        total = duration_hint or 0.0
        if total <= 0 and ranges:
            total = max(r.end for r in ranges)
        coverage = (speech_dur / total) if total > 0 else (1.0 if ranges else 0.0)
        coverage = max(0.0, min(1.0, coverage))
        return SpeakerPresence(speech_ranges=ranges, estimated_speech_coverage=coverage)

    def _write_report(
        self,
        project_id: str,
        root: Path,
        report: VideoAnalysisReport,
    ) -> Path:
        path = root / "analysis" / "video_analysis.json"
        try:
            try:
                canonical = get_video_analysis_path(project_id)
                if canonical.parent.parent == root.resolve():
                    path = canonical
            except Exception:  # noqa: BLE001
                pass
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                ensure_project_analysis_dir(project_id)
            except Exception:  # noqa: BLE001
                pass
            path.write_text(
                json.dumps(report.model_dump(mode="json"), indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            raise StorageError(f"Failed to write video analysis: {path}") from exc
        return path.resolve()
