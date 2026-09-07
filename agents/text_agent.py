"""Text/Script Agent — clean, analyze, and structure user-provided text."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from agents.base import BaseAgent
from config.settings import get_settings
from core.errors import StorageError, TextAgentError
from core.logging import get_logger
from core.paths import (
    ensure_project_dir,
    ensure_project_source_dir,
    get_transcript_path,
)
from schemas.job import SourceType
from schemas.project import ProjectMetadata
from schemas.transcript import (
    ClipBoundary,
    GeminiScriptAnalysis,
    HookCandidate,
    ImportantStatement,
    ScriptSection,
    StructuredTranscript,
    TextAgentResult,
)
from schemas.youtube import YouTubeSourceMetadata, YouTubeSourceStatus
from tools.llm.gemini import analyze_script_structure
from tools.text.cleaning import clean_text
from tools.text.sectioning import build_logical_sections
from tools.text.segmenting import split_paragraphs, split_sentences

logger = get_logger(__name__)

AnalyzeFn = Callable[..., GeminiScriptAnalysis]


class TextAgent(BaseAgent):
    """Process script/article/transcript text into a structured transcript."""

    name = "text"

    def __init__(self, analyze_fn: AnalyzeFn | None = None) -> None:
        self._analyze_fn = analyze_fn or analyze_script_structure

    def run(
        self,
        project: ProjectMetadata | dict[str, Any],
        project_dir: str | Path | None = None,
        **_: Any,
    ) -> TextAgentResult:
        meta = self._coerce_project(project)
        raw = (meta.raw_text or "").strip()
        if not raw:
            raise TextAgentError("Project is missing script text (raw_text).")

        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)

        cleaned = clean_text(raw)
        if not cleaned:
            raise TextAgentError("Script text is empty after cleaning.")

        sentences = split_sentences(cleaned)
        paragraphs = split_paragraphs(cleaned, sentences)
        sections = build_logical_sections(cleaned, paragraphs, sentences)

        try:
            analysis = self._analyze_fn(cleaned, sentences, sections)
        except TextAgentError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise TextAgentError(f"Script analysis failed: {exc}") from exc

        if not isinstance(analysis, GeminiScriptAnalysis):
            analysis = GeminiScriptAnalysis.model_validate(analysis)

        sections = self._apply_section_titles(sections, analysis.section_titles)
        hooks = self._map_hooks(analysis, sentences)
        important = self._map_important(analysis, sentences)
        boundaries = self._map_boundaries(analysis, sentences)

        transcript = StructuredTranscript(
            project_id=project_id,
            source_type=SourceType.SCRIPT,
            language=analysis.language or "unknown",
            topics=list(analysis.topics or []),
            cleaned_text=cleaned,
            sentences=sentences,
            paragraphs=paragraphs,
            sections=sections,
            hooks=hooks,
            important_statements=important,
            clip_boundaries=boundaries,
            provider="gemini" if get_settings().has_gemini_api_key else "heuristic",
        )

        transcript_path = self._write_transcript(project_id, root, transcript)
        source_dir, source_meta = self._write_source_parity(
            project_id, root, transcript, hooks, sections
        )

        messages = [
            f"[{self.name}] Cleaned script ({len(cleaned)} chars)",
            f"[{self.name}] Language: {transcript.language}",
            f"[{self.name}] Topics: {', '.join(transcript.topics) or '(none)'}",
            f"[{self.name}] Sentences: {len(sentences)}, paragraphs: {len(paragraphs)}, sections: {len(sections)}",
            f"[{self.name}] Hooks: {len(hooks)}, important: {len(important)}, clip boundaries: {len(boundaries)}",
            f"[{self.name}] Wrote transcript.json",
            f"[{self.name}] Passing structured transcript to video understanding pipeline.",
        ]
        logger.info(
            "TextAgent ready project_id=%s sentences=%s sections=%s",
            project_id,
            len(sentences),
            len(sections),
        )
        return TextAgentResult(
            transcript=transcript,
            transcript_path=str(transcript_path),
            source_dir=source_dir,
            source_metadata=source_meta,
            messages=messages,
        )

    def _coerce_project(self, project: ProjectMetadata | dict[str, Any]) -> ProjectMetadata:
        if isinstance(project, ProjectMetadata):
            return project
        try:
            return ProjectMetadata.model_validate(project)
        except Exception as exc:  # noqa: BLE001
            raise TextAgentError(f"Invalid project metadata: {exc}") from exc

    def _apply_section_titles(
        self,
        sections: list[ScriptSection],
        titles: list[str],
    ) -> list[ScriptSection]:
        updated: list[ScriptSection] = []
        for i, sec in enumerate(sections):
            title = titles[i].strip() if i < len(titles) and titles[i] else sec.title
            updated.append(sec.model_copy(update={"title": title or f"Section {i + 1}"}))
        return updated

    def _map_hooks(self, analysis: GeminiScriptAnalysis, sentences) -> list[HookCandidate]:
        out: list[HookCandidate] = []
        for hook in analysis.hooks:
            sent = self._sentence_by_index(sentences, hook.sentence_index)
            if sent is None:
                continue
            out.append(
                HookCandidate(
                    text=sent.text,
                    sentence_id=sent.id,
                    reason=hook.reason,
                    score=hook.score,
                )
            )
        return out

    def _map_important(
        self, analysis: GeminiScriptAnalysis, sentences
    ) -> list[ImportantStatement]:
        out: list[ImportantStatement] = []
        for item in analysis.important_statements:
            sent = self._sentence_by_index(sentences, item.sentence_index)
            if sent is None:
                continue
            out.append(
                ImportantStatement(
                    text=sent.text,
                    sentence_id=sent.id,
                    reason=item.reason,
                )
            )
        return out

    def _map_boundaries(
        self, analysis: GeminiScriptAnalysis, sentences
    ) -> list[ClipBoundary]:
        out: list[ClipBoundary] = []
        for boundary in analysis.clip_boundaries:
            sent = self._sentence_by_index(sentences, boundary.after_sentence_index)
            if sent is None:
                continue
            out.append(
                ClipBoundary(
                    after_sentence_id=sent.id,
                    reason=boundary.reason,
                    suggested_title=boundary.suggested_title,
                )
            )
        return out

    def _sentence_by_index(self, sentences, index: int):
        for sent in sentences:
            if sent.index == index:
                return sent
        if 0 <= index < len(sentences):
            return sentences[index]
        return None

    def _write_transcript(
        self,
        project_id: str,
        root: Path,
        transcript: StructuredTranscript,
    ) -> Path:
        # Prefer project layout under outputs; also support custom root in tests
        path = root / "transcript.json"
        try:
            # Keep canonical path helper in sync when using default layout
            canonical = get_transcript_path(project_id)
            if canonical.parent == root.resolve() or root.resolve() == canonical.parent:
                path = canonical
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(transcript.model_dump(mode="json"), indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            raise StorageError(f"Failed to write transcript.json: {path}") from exc
        return path.resolve()

    def _write_source_parity(
        self,
        project_id: str,
        root: Path,
        transcript: StructuredTranscript,
        hooks: list[HookCandidate],
        sections: list[ScriptSection],
    ) -> tuple[str, dict[str, Any]]:
        source_dir = root / "source"
        try:
            source_dir.mkdir(parents=True, exist_ok=True)
            # Also ensure via helper when using standard project id layout
            try:
                ensure_project_source_dir(project_id)
            except Exception:  # noqa: BLE001
                pass

            title = ""
            if hooks:
                title = hooks[0].text[:120]
            elif sections:
                title = sections[0].title
            title = title or "Script input"

            meta = YouTubeSourceMetadata(
                url="",
                canonical_url="",
                video_id="",
                title=title,
                channel="script",
                duration_seconds=None,
                source_status=YouTubeSourceStatus.READY_FOR_PIPELINE,
                provider="text_agent",
                notes="Script/text input — structured transcript ready for pipeline.",
            )
            meta_path = source_dir / "source_metadata.json"
            meta_path.write_text(
                json.dumps(meta.model_dump(mode="json"), indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            raise StorageError(f"Failed to write source metadata: {source_dir}") from exc

        return str(source_dir.resolve()), meta.model_dump(mode="json")
