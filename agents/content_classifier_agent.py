"""Content Classifier Agent — auto-detect video content type from transcript + scenes.

Runs after transcript + speaker analysis.  Returns content_type, is_podcast,
speaker_roles, etc.  Used by the Supervisor to route into the correct pipeline.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agents.base import BaseAgent
from core.logging import get_logger
from core.paths import ensure_project_analysis_dir, ensure_project_dir
from schemas.project import ProjectMetadata

logger = get_logger(__name__)

CONTENT_TYPES = (
    "podcast",
    "interview",
    "talking_head",
    "vlog",
    "lecture",
    "documentary",
    "news",
    "gameplay",
    "reaction",
    "tutorial",
    "unknown",
)


class ContentClassifierAgent(BaseAgent):
    """Write analysis/content_classification.json with auto-detected content type."""

    name = "content_classifier"

    def run(
        self,
        project: ProjectMetadata | dict[str, Any],
        *,
        project_dir: str | Path | None = None,
        transcript: dict[str, Any] | None = None,
        speech_transcript: dict[str, Any] | None = None,
        speakers: dict[str, Any] | None = None,
        scenes: dict[str, Any] | None = None,
        analysis: dict[str, Any] | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        meta = self._coerce_project(project)
        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)

        result = self._classify(
            transcript=transcript,
            speech_transcript=speech_transcript,
            speakers=speakers,
            scenes=scenes,
            analysis=analysis,
        )

        path = self._write(project_id, root, result)
        logger.info(
            "ContentClassifier project_id=%s type=%s is_podcast=%s",
            project_id,
            result.get("content_type"),
            result.get("is_podcast"),
        )
        return {
            "content_classification": result,
            "content_classification_path": str(path),
            "messages": [
                f"[{self.name}] Content type: {result.get('content_type')} "
                f"(is_podcast={result.get('is_podcast')})"
            ],
        }

    # ------------------------------------------------------------------
    # Classification logic
    # ------------------------------------------------------------------

    def _classify(
        self,
        *,
        transcript: dict[str, Any] | None,
        speech_transcript: dict[str, Any] | None,
        speakers: dict[str, Any] | None,
        scenes: dict[str, Any] | None,
        analysis: dict[str, Any] | None,
    ) -> dict[str, Any]:
        # Try Gemini-based classification first
        try:
            return self._classify_gemini(
                transcript=transcript,
                speech_transcript=speech_transcript,
                speakers=speakers,
                scenes=scenes,
                analysis=analysis,
            )
        except Exception as exc:  # noqa: BLE001
            logger.info("Gemini content classification skipped: %s — using heuristic.", exc)

        return self._classify_heuristic(
            transcript=transcript,
            speech_transcript=speech_transcript,
            speakers=speakers,
            scenes=scenes,
        )

    def _classify_gemini(
        self,
        *,
        transcript: dict[str, Any] | None,
        speech_transcript: dict[str, Any] | None,
        speakers: dict[str, Any] | None,
        scenes: dict[str, Any] | None,
        analysis: dict[str, Any] | None,
    ) -> dict[str, Any]:
        from tools.llm.gemini import call_gemini_json

        # Build context block
        text = self._extract_text(transcript, speech_transcript)[:3000]
        n_speakers = self._count_speakers(speakers)
        n_scenes = self._count_scenes(scenes)

        prompt = f"""You are a video content classifier.

Based on the following data, classify this video content.

Transcript excerpt:
{text}

Number of distinct speakers: {n_speakers}
Number of detected scenes: {n_scenes}

Classify the content type as one of:
podcast, interview, talking_head, vlog, lecture, documentary, news, gameplay, reaction, tutorial, unknown

If the content type is "podcast" or "interview", also identify:
- is_host: speaker label(s) that appear to be the host
- is_guest: speaker label(s) that appear to be the guest(s)

Return JSON:
{{
  "content_type": "<type>",
  "is_podcast": true/false,
  "confidence": 0.0-1.0,
  "speaker_roles": {{"<speaker_id>": "host|guest|narrator|unknown"}},
  "reasoning": "<one sentence>"
}}"""

        raw = call_gemini_json(prompt)
        if not isinstance(raw, dict):
            raise ValueError("Gemini returned non-dict")

        content_type = str(raw.get("content_type", "unknown")).lower()
        if content_type not in CONTENT_TYPES:
            content_type = "unknown"

        return {
            "content_type": content_type,
            "is_podcast": bool(raw.get("is_podcast", content_type in ("podcast", "interview"))),
            "confidence": float(raw.get("confidence", 0.7)),
            "speaker_roles": raw.get("speaker_roles") or {},
            "reasoning": str(raw.get("reasoning", "")),
            "method": "gemini",
        }

    def _classify_heuristic(
        self,
        *,
        transcript: dict[str, Any] | None,
        speech_transcript: dict[str, Any] | None,
        speakers: dict[str, Any] | None,
        scenes: dict[str, Any] | None,
    ) -> dict[str, Any]:
        n_speakers = self._count_speakers(speakers)
        text = self._extract_text(transcript, speech_transcript).lower()

        # Keyword signals
        podcast_keywords = {"podcast", "episode", "interview", "host", "guest", "listener", "subscribe", "spotify", "patreon"}
        vlog_keywords = {"today", "my day", "vlog", "come with me", "daily"}
        lecture_keywords = {"today we'll", "in this video", "let's learn", "tutorial", "step by step"}
        news_keywords = {"breaking", "report", "according to", "officials", "announced"}

        scores: dict[str, float] = {t: 0.0 for t in CONTENT_TYPES}

        for kw in podcast_keywords:
            if kw in text:
                scores["podcast"] += 1.0
        for kw in vlog_keywords:
            if kw in text:
                scores["vlog"] += 1.0
        for kw in lecture_keywords:
            if kw in text:
                scores["lecture"] += 1.0
        for kw in news_keywords:
            if kw in text:
                scores["news"] += 1.0

        # Speaker count heuristic
        if n_speakers >= 2:
            scores["podcast"] += 2.0
            scores["interview"] += 1.5
        elif n_speakers == 1:
            scores["talking_head"] += 1.0
            scores["lecture"] += 0.5

        best = max(scores, key=lambda k: scores[k])
        best_score = scores[best]
        if best_score < 1.0:
            best = "unknown"

        is_podcast = best in ("podcast", "interview")

        # Simple speaker role assignment
        speaker_roles: dict[str, str] = {}
        if isinstance(speakers, dict):
            spk_list = speakers.get("speakers") or []
            if isinstance(spk_list, list):
                for i, spk in enumerate(spk_list):
                    sid = str(spk.get("id") or spk.get("speaker_id") or f"speaker_{i}")
                    speaker_roles[sid] = "host" if i == 0 else "guest"

        return {
            "content_type": best,
            "is_podcast": is_podcast,
            "confidence": round(min(best_score / 5.0, 1.0), 2),
            "speaker_roles": speaker_roles,
            "reasoning": f"Heuristic: keyword + speaker count (n={n_speakers}).",
            "method": "heuristic",
        }

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_text(
        transcript: dict[str, Any] | None,
        speech_transcript: dict[str, Any] | None,
    ) -> str:
        for blob in (transcript, speech_transcript):
            if not isinstance(blob, dict):
                continue
            for key in ("text", "full_text", "cleaned_text"):
                val = str(blob.get(key) or "").strip()
                if val:
                    return val
        return ""

    @staticmethod
    def _count_speakers(speakers: dict[str, Any] | None) -> int:
        if not isinstance(speakers, dict):
            return 0
        spk_list = speakers.get("speakers") or []
        if isinstance(spk_list, list):
            return len(spk_list)
        return int(speakers.get("speaker_count") or 0)

    @staticmethod
    def _count_scenes(scenes: dict[str, Any] | None) -> int:
        if not isinstance(scenes, dict):
            return 0
        sc = scenes.get("scenes") or []
        return len(sc) if isinstance(sc, list) else 0

    def _coerce_project(self, project: ProjectMetadata | dict[str, Any]) -> ProjectMetadata:
        if isinstance(project, ProjectMetadata):
            return project
        return ProjectMetadata.model_validate(project)

    def _write(self, project_id: str, root: Path, result: dict[str, Any]) -> Path:
        try:
            ensure_project_analysis_dir(project_id)
        except Exception:  # noqa: BLE001
            pass
        path = root / "analysis" / "content_classification.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        return path
