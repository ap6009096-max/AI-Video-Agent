"""Story Agent — HOOK→CONTEXT→VALUE/EVENT→PAYOFF→CTA per selected clip."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from agents.base import BaseAgent
from core.errors import StorageError, StoryAgentError
from core.logging import get_logger
from core.paths import (
    ensure_project_analysis_dir,
    ensure_project_dir,
    get_stories_path,
)
from schemas.clips import ClipCandidate, ClipsReport
from schemas.job import SourceType, VideoJobConfig
from schemas.project import ProjectMetadata
from schemas.story import (
    ClipStory,
    GeminiClipStory,
    GeminiStoriesBatch,
    StoriesReport,
    StoryAgentResult,
    StoryStructure,
)
from schemas.video_type import VideoTypePack
from schemas.environment import EnvironmentPack
from schemas.visual_style import VisualStylePack
from tools.environments.catalog import environment_prompt_block
from tools.video_types.catalog import video_type_prompt_block
from tools.visual_styles.catalog import visual_style_prompt_block

logger = get_logger(__name__)

GenerateStoriesFn = Callable[..., GeminiStoriesBatch]


def _truncate(text: str, max_len: int = 120) -> str:
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    cut = text[: max_len - 1].rsplit(" ", 1)[0]
    return (cut or text[: max_len - 1]).rstrip() + "…"


def _overlap_text_from_segments(
    segments: list[dict[str, Any]],
    start: float,
    end: float,
) -> str:
    parts: list[str] = []
    for seg in segments:
        try:
            s = float(seg.get("start", 0.0))
            e = float(seg.get("end", s))
        except (TypeError, ValueError):
            continue
        if e < start or s > end:
            continue
        text = str(seg.get("text") or "").strip()
        if text:
            parts.append(text)
    return " ".join(parts).strip()


def _overlap_text_from_sentences(
    sentences: list[dict[str, Any]],
    start: float,
    end: float,
) -> str:
    """Prefer timed sentences; otherwise return empty (caller falls back)."""
    timed: list[str] = []
    for sent in sentences:
        s_raw = sent.get("start_seconds", sent.get("start"))
        e_raw = sent.get("end_seconds", sent.get("end"))
        if s_raw is None or e_raw is None:
            continue
        try:
            s = float(s_raw)
            e = float(e_raw)
        except (TypeError, ValueError):
            continue
        if e < start or s > end:
            continue
        text = str(sent.get("text") or "").strip()
        if text:
            timed.append(text)
    return " ".join(timed).strip()


def resolve_source_excerpt(
    clip: ClipCandidate,
    *,
    transcript: dict[str, Any] | None = None,
    speech_transcript: dict[str, Any] | None = None,
    prefer_original_transcript: bool = True,
) -> str:
    """Grounding text for a clip — prefer clip.transcript, then timed speech/script."""
    clip_text = (clip.transcript or "").strip()
    if clip_text:
        return clip_text

    if prefer_original_transcript and speech_transcript:
        segments = speech_transcript.get("segments") or []
        if isinstance(segments, list) and segments:
            excerpt = _overlap_text_from_segments(segments, clip.start, clip.end)
            if excerpt:
                return excerpt
        full = str(speech_transcript.get("text") or "").strip()
        if full:
            return full

    if transcript:
        sentences = transcript.get("sentences") or []
        if isinstance(sentences, list) and sentences:
            excerpt = _overlap_text_from_sentences(sentences, clip.start, clip.end)
            if excerpt:
                return excerpt
        cleaned = str(transcript.get("cleaned_text") or "").strip()
        if cleaned:
            return cleaned

    return ""


class StoryAgent(BaseAgent):
    """Write analysis/stories.json from selected clips via Gemini."""

    name = "story"

    def __init__(self, generate_fn: GenerateStoriesFn | None = None) -> None:
        self._generate_fn = generate_fn

    def run(
        self,
        project: ProjectMetadata | dict[str, Any],
        *,
        project_dir: str | Path | None = None,
        clips: dict[str, Any] | ClipsReport | None = None,
        transcript: dict[str, Any] | None = None,
        speech_transcript: dict[str, Any] | None = None,
        config: VideoJobConfig | dict[str, Any] | None = None,
        video_type_pack: dict[str, Any] | VideoTypePack | None = None,
        visual_style_pack: dict[str, Any] | VisualStylePack | None = None,
        environment_pack: dict[str, Any] | EnvironmentPack | None = None,
        research_report: dict[str, Any] | None = None,
        **_: Any,
    ) -> StoryAgentResult:
        meta = self._coerce_project(project)
        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)
        job_config = self._coerce_config(config)
        clip_list = self._parse_clips(clips)
        type_block = self._video_type_block(video_type_pack, job_config)
        style_block = self._visual_style_block(visual_style_pack)
        env_block = self._environment_block(environment_pack)
        from tools.research.build import format_research_grounding_block

        research_block = format_research_grounding_block(research_report)

        if not clip_list:
            notes = "No clips selected — story generation skipped."
            report = StoriesReport(
                project_id=project_id,
                stories=[],
                provider="skipped",
                notes=notes,
            )
            path = self._write_report(project_id, root, report)
            return StoryAgentResult(
                stories=report,
                stories_path=str(path),
                messages=[f"[{self.name}] {notes}"],
            )

        prefer_original = meta.source_type in (SourceType.YOUTUBE, SourceType.UPLOAD)
        payloads: list[tuple[ClipCandidate, str]] = []
        clip_blocks: list[str] = []
        for clip in clip_list:
            excerpt = resolve_source_excerpt(
                clip,
                transcript=transcript,
                speech_transcript=speech_transcript,
                prefer_original_transcript=prefer_original,
            )
            payloads.append((clip, excerpt))
            soft = []
            if clip.category:
                soft.append(f"category={clip.category}")
            if clip.reason:
                soft.append(f"reason={clip.reason}")
            if clip.evidence:
                soft.append(f"evidence={'; '.join(clip.evidence[:5])}")
            soft_line = f"\nSoft context (not facts): {'; '.join(soft)}" if soft else ""
            clip_blocks.append(
                f"### clip_id={clip.id} start={clip.start:.2f} end={clip.end:.2f}\n"
                f"Source excerpt:\n{excerpt or '(empty)'}"
                f"{soft_line}"
            )

        try:
            from tools.llm.gemini import generate_clip_stories

            generate = self._generate_fn or generate_clip_stories
            batch = generate(
                clip_blocks,
                project_id=project_id,
                video_type=job_config.video_type,
                country=job_config.country,
                video_type_block=type_block,
                visual_style_block=style_block,
                environment_block=env_block,
                research_block=research_block,
            )
        except StoryAgentError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise StoryAgentError(f"Story generation failed: {exc}") from exc

        if not isinstance(batch, GeminiStoriesBatch):
            batch = GeminiStoriesBatch.model_validate(batch)

        by_id = {s.clip_id: s for s in batch.stories}
        stories: list[ClipStory] = []
        for clip, excerpt in payloads:
            gem = by_id.get(clip.id)
            structure = self._structure_from_gemini(gem, excerpt)
            stories.append(
                ClipStory(
                    clip_id=clip.id,
                    start=clip.start,
                    end=clip.end,
                    structure=structure,
                    source_excerpt=excerpt,
                )
            )

        report = StoriesReport(
            project_id=project_id,
            stories=stories,
            provider="gemini-story",
            notes=(
                "Stories grounded in clip source excerpts; "
                "no unsupported claims should be fabricated."
                + (" Research grounding attached." if research_block else "")
            ),
        )
        path = self._write_report(project_id, root, report)
        messages = [
            f"[{self.name}] Generated stories: {len(stories)}",
            f"[{self.name}] Wrote analysis/stories.json",
        ]
        logger.info(
            "StoryAgent ready project_id=%s count=%s",
            project_id,
            len(stories),
        )
        return StoryAgentResult(
            stories=report,
            stories_path=str(path),
            messages=messages,
        )

    def _structure_from_gemini(
        self,
        gem: GeminiClipStory | None,
        excerpt: str,
    ) -> StoryStructure:
        fallback = _truncate(excerpt) if excerpt else ""
        if gem is None:
            return StoryStructure(
                hook=fallback,
                context="",
                value_event=fallback,
                payoff="",
                cta="",
            )
        return StoryStructure(
            hook=(gem.hook or "").strip() or fallback,
            context=(gem.context or "").strip(),
            value_event=(gem.value_event or "").strip() or fallback,
            payoff=(gem.payoff or "").strip(),
            cta=(gem.cta or "").strip(),
        )

    def _parse_clips(
        self, clips: dict[str, Any] | ClipsReport | None
    ) -> list[ClipCandidate]:
        if clips is None:
            return []
        if isinstance(clips, ClipsReport):
            return list(clips.clips)
        try:
            report = ClipsReport.model_validate(clips)
            return list(report.clips)
        except Exception:
            raw = clips.get("clips") if isinstance(clips, dict) else None
            if not isinstance(raw, list):
                return []
            out: list[ClipCandidate] = []
            for item in raw:
                try:
                    out.append(
                        item
                        if isinstance(item, ClipCandidate)
                        else ClipCandidate.model_validate(item)
                    )
                except Exception:  # noqa: BLE001
                    continue
            return out

    def _coerce_project(self, project: ProjectMetadata | dict[str, Any]) -> ProjectMetadata:
        if isinstance(project, ProjectMetadata):
            return project
        try:
            return ProjectMetadata.model_validate(project)
        except Exception as exc:  # noqa: BLE001
            raise StoryAgentError(f"Invalid project metadata: {exc}") from exc

    def _coerce_config(
        self, config: VideoJobConfig | dict[str, Any] | None
    ) -> VideoJobConfig:
        if config is None:
            return VideoJobConfig()
        if isinstance(config, VideoJobConfig):
            return config
        try:
            return VideoJobConfig.model_validate(config)
        except Exception as exc:  # noqa: BLE001
            raise StoryAgentError(f"Invalid job config: {exc}") from exc

    def _video_type_block(
        self,
        video_type_pack: dict[str, Any] | VideoTypePack | None,
        job_config: VideoJobConfig,
    ) -> str:
        pack: VideoTypePack | None = None
        if isinstance(video_type_pack, VideoTypePack):
            pack = video_type_pack
        elif isinstance(video_type_pack, dict) and video_type_pack:
            try:
                pack = VideoTypePack.model_validate(video_type_pack)
            except Exception:  # noqa: BLE001
                pack = None
        if pack is None:
            return ""
        return video_type_prompt_block(pack)

    def _visual_style_block(
        self,
        visual_style_pack: dict[str, Any] | VisualStylePack | None,
    ) -> str:
        pack: VisualStylePack | None = None
        if isinstance(visual_style_pack, VisualStylePack):
            pack = visual_style_pack
        elif isinstance(visual_style_pack, dict) and visual_style_pack:
            try:
                pack = VisualStylePack.model_validate(visual_style_pack)
            except Exception:  # noqa: BLE001
                pack = None
        if pack is None:
            return ""
        return visual_style_prompt_block(pack)

    def _environment_block(
        self,
        environment_pack: dict[str, Any] | EnvironmentPack | None,
    ) -> str:
        pack: EnvironmentPack | None = None
        if isinstance(environment_pack, EnvironmentPack):
            pack = environment_pack
        elif isinstance(environment_pack, dict) and environment_pack:
            try:
                pack = EnvironmentPack.model_validate(environment_pack)
            except Exception:  # noqa: BLE001
                pack = None
        if pack is None:
            return ""
        return environment_prompt_block(pack)

    def _write_report(
        self,
        project_id: str,
        root: Path,
        report: StoriesReport,
    ) -> Path:
        path = root / "analysis" / "stories.json"
        try:
            try:
                canonical = get_stories_path(project_id)
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
            raise StorageError(f"Failed to write stories.json: {path}") from exc
        return path.resolve()
