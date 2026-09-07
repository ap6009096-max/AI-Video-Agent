"""Script Agent — title/hook/script/caption/CTA/thumbnail/keywords per clip."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from agents.base import BaseAgent
from agents.story_agent import resolve_source_excerpt
from core.errors import ScriptAgentError, StorageError
from core.logging import get_logger
from core.paths import (
    ensure_project_analysis_dir,
    ensure_project_dir,
    get_scripts_path,
)
from schemas.clips import ClipCandidate, ClipsReport
from schemas.job import VideoJobConfig
from schemas.project import ProjectMetadata
from schemas.story import (
    ClipScript,
    ClipStory,
    GeminiClipScript,
    GeminiScriptsBatch,
    ScriptAgentResult,
    ScriptsReport,
    StoriesReport,
    StoryStructure,
)
from schemas.video_type import VideoTypePack
from schemas.environment import EnvironmentPack
from schemas.visual_style import VisualStylePack
from tools.environments.catalog import environment_prompt_block
from tools.video_types.catalog import video_type_prompt_block
from tools.visual_styles.catalog import visual_style_prompt_block

logger = get_logger(__name__)

GenerateScriptsFn = Callable[..., GeminiScriptsBatch]


def _truncate(text: str, max_len: int = 80) -> str:
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    cut = text[: max_len - 1].rsplit(" ", 1)[0]
    return (cut or text[: max_len - 1]).rstrip() + "…"


def _thumbnail_words(text: str, max_words: int = 5) -> str:
    words = [w for w in (text or "").split() if w]
    return " ".join(words[:max_words])


class ScriptAgent(BaseAgent):
    """Write analysis/scripts.json from stories + clip source via Gemini."""

    name = "script"

    def __init__(self, generate_fn: GenerateScriptsFn | None = None) -> None:
        self._generate_fn = generate_fn

    def run(
        self,
        project: ProjectMetadata | dict[str, Any],
        *,
        project_dir: str | Path | None = None,
        clips: dict[str, Any] | ClipsReport | None = None,
        stories: dict[str, Any] | StoriesReport | None = None,
        transcript: dict[str, Any] | None = None,
        speech_transcript: dict[str, Any] | None = None,
        config: VideoJobConfig | dict[str, Any] | None = None,
        video_type_pack: dict[str, Any] | VideoTypePack | None = None,
        visual_style_pack: dict[str, Any] | VisualStylePack | None = None,
        environment_pack: dict[str, Any] | EnvironmentPack | None = None,
        research_report: dict[str, Any] | None = None,
        **_: Any,
    ) -> ScriptAgentResult:
        meta = self._coerce_project(project)
        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)
        job_config = self._coerce_config(config)
        clip_list = self._parse_clips(clips)
        story_list = self._parse_stories(stories)
        stories_by_id = {s.clip_id: s for s in story_list}
        type_block = self._video_type_block(video_type_pack, job_config)
        style_block = self._visual_style_block(visual_style_pack)
        env_block = self._environment_block(environment_pack)
        from tools.research.build import format_research_grounding_block

        research_block = format_research_grounding_block(research_report)

        if not clip_list or not story_list:
            notes = "No stories/clips available — script generation skipped."
            report = ScriptsReport(
                project_id=project_id,
                scripts=[],
                provider="skipped",
                notes=notes,
            )
            path = self._write_report(project_id, root, report)
            return ScriptAgentResult(
                scripts=report,
                scripts_path=str(path),
                messages=[f"[{self.name}] {notes}"],
            )

        clips_by_id = {c.id: c for c in clip_list}
        clip_blocks: list[str] = []
        ordered_stories: list[ClipStory] = []
        for story in story_list:
            clip = clips_by_id.get(story.clip_id)
            excerpt = story.source_excerpt.strip()
            if not excerpt and clip is not None:
                excerpt = resolve_source_excerpt(
                    clip,
                    transcript=transcript,
                    speech_transcript=speech_transcript,
                    prefer_original_transcript=True,
                )
            struct = story.structure
            clip_blocks.append(
                f"### clip_id={story.clip_id}\n"
                f"Source excerpt:\n{excerpt or '(empty)'}\n\n"
                f"Story structure:\n"
                f"- HOOK: {struct.hook}\n"
                f"- CONTEXT: {struct.context}\n"
                f"- VALUE/EVENT: {struct.value_event}\n"
                f"- PAYOFF: {struct.payoff}\n"
                f"- CTA: {struct.cta}"
            )
            ordered_stories.append(story)

        try:
            from tools.llm.gemini import generate_clip_scripts

            generate = self._generate_fn or generate_clip_scripts
            batch = generate(
                clip_blocks,
                video_type=job_config.video_type,
                country=job_config.country,
                video_type_block=type_block,
                visual_style_block=style_block,
                environment_block=env_block,
                research_block=research_block,
            )
        except ScriptAgentError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ScriptAgentError(f"Script generation failed: {exc}") from exc

        if not isinstance(batch, GeminiScriptsBatch):
            batch = GeminiScriptsBatch.model_validate(batch)

        by_id = {s.clip_id: s for s in batch.scripts}
        scripts: list[ClipScript] = []
        for story in ordered_stories:
            gem = by_id.get(story.clip_id)
            scripts.append(self._script_from_gemini(gem, story))

        report = ScriptsReport(
            project_id=project_id,
            scripts=scripts,
            provider="gemini-script",
            notes=(
                "Scripts derived from story structure and source excerpts only."
                + (" Research grounding attached." if research_block else "")
            ),
        )
        path = self._write_report(project_id, root, report)
        messages = [
            f"[{self.name}] Generated scripts: {len(scripts)}",
            f"[{self.name}] Wrote analysis/scripts.json",
        ]
        logger.info(
            "ScriptAgent ready project_id=%s count=%s",
            project_id,
            len(scripts),
        )
        return ScriptAgentResult(
            scripts=report,
            scripts_path=str(path),
            messages=messages,
        )

    def _script_from_gemini(
        self,
        gem: GeminiClipScript | None,
        story: ClipStory,
    ) -> ClipScript:
        excerpt = story.source_excerpt
        struct = story.structure
        fallback_hook = (struct.hook or _truncate(excerpt)).strip()
        fallback_title = _truncate(fallback_hook, 60)
        fallback_cta = (struct.cta or "").strip()
        fallback_script = " ".join(
            p
            for p in (
                struct.hook,
                struct.context,
                struct.value_event,
                struct.payoff,
                struct.cta,
            )
            if (p or "").strip()
        ).strip() or excerpt

        if gem is None:
            return ClipScript(
                clip_id=story.clip_id,
                title=fallback_title,
                hook=fallback_hook,
                short_script=fallback_script,
                caption=_truncate(fallback_script, 200),
                cta=fallback_cta,
                thumbnail_text=_thumbnail_words(fallback_hook),
                keywords=[],
                story_structure=struct,
            )

        title = (gem.title or "").strip() or fallback_title
        hook = (gem.hook or "").strip() or fallback_hook
        short_script = (gem.short_script or "").strip() or fallback_script
        caption = (gem.caption or "").strip() or _truncate(short_script, 200)
        cta = (gem.cta or "").strip() or fallback_cta
        thumbnail = (gem.thumbnail_text or "").strip() or _thumbnail_words(hook)
        keywords = [k.strip() for k in (gem.keywords or []) if str(k).strip()]

        return ClipScript(
            clip_id=story.clip_id,
            title=title,
            hook=hook,
            short_script=short_script,
            caption=caption,
            cta=cta,
            thumbnail_text=thumbnail,
            keywords=keywords,
            story_structure=StoryStructure.model_validate(struct.model_dump()),
        )

    def _parse_clips(
        self, clips: dict[str, Any] | ClipsReport | None
    ) -> list[ClipCandidate]:
        if clips is None:
            return []
        if isinstance(clips, ClipsReport):
            return list(clips.clips)
        try:
            return list(ClipsReport.model_validate(clips).clips)
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

    def _parse_stories(
        self, stories: dict[str, Any] | StoriesReport | None
    ) -> list[ClipStory]:
        if stories is None:
            return []
        if isinstance(stories, StoriesReport):
            return list(stories.stories)
        try:
            return list(StoriesReport.model_validate(stories).stories)
        except Exception:
            raw = stories.get("stories") if isinstance(stories, dict) else None
            if not isinstance(raw, list):
                return []
            out: list[ClipStory] = []
            for item in raw:
                try:
                    out.append(
                        item
                        if isinstance(item, ClipStory)
                        else ClipStory.model_validate(item)
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
            raise ScriptAgentError(f"Invalid project metadata: {exc}") from exc

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
            raise ScriptAgentError(f"Invalid job config: {exc}") from exc

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
        report: ScriptsReport,
    ) -> Path:
        path = root / "analysis" / "scripts.json"
        try:
            try:
                canonical = get_scripts_path(project_id)
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
            raise StorageError(f"Failed to write scripts.json: {path}") from exc
        return path.resolve()
