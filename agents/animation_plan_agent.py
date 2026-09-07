"""Animation Plan Agent — generate per-scene animation specification JSON.

Converts transcript + speaker data into a structured visual plan for an
Animated Podcast output.  Does NOT call any external image/video generation API.
The animation_plan.json is a first-class deliverable describing exactly what
each scene should look like — suitable for human review or downstream rendering.
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


class AnimationPlanAgent(BaseAgent):
    """Write analysis/animation_plan.json from transcript + speaker data."""

    name = "animation_plan"

    def run(
        self,
        project: ProjectMetadata | dict[str, Any],
        *,
        project_dir: str | Path | None = None,
        transcript: dict[str, Any] | None = None,
        speech_transcript: dict[str, Any] | None = None,
        speakers: dict[str, Any] | None = None,
        scenes: dict[str, Any] | None = None,
        content_classification: dict[str, Any] | None = None,
        funny_moments: dict[str, Any] | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        meta = self._coerce_project(project)
        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)

        plan = self._build_plan(
            transcript=transcript,
            speech_transcript=speech_transcript,
            speakers=speakers,
            scenes=scenes,
            content_classification=content_classification,
            funny_moments=funny_moments,
        )

        path = self._write(project_id, root, plan)
        n_scenes = len(plan.get("scenes", []))
        logger.info("AnimationPlanAgent project_id=%s scenes=%d", project_id, n_scenes)
        return {
            "animation_plan": plan,
            "animation_plan_path": str(path),
            "messages": [
                f"[{self.name}] Animation plan: {n_scenes} scenes",
                f"[{self.name}] Wrote analysis/animation_plan.json",
            ],
        }

    # ------------------------------------------------------------------
    # Plan building
    # ------------------------------------------------------------------

    def _build_plan(
        self,
        *,
        transcript: dict[str, Any] | None,
        speech_transcript: dict[str, Any] | None,
        speakers: dict[str, Any] | None,
        scenes: dict[str, Any] | None,
        content_classification: dict[str, Any] | None,
        funny_moments: dict[str, Any] | None,
    ) -> dict[str, Any]:
        try:
            return self._build_gemini(
                transcript=transcript,
                speech_transcript=speech_transcript,
                speakers=speakers,
                scenes=scenes,
                content_classification=content_classification,
                funny_moments=funny_moments,
            )
        except Exception as exc:  # noqa: BLE001
            logger.info("Gemini animation plan skipped: %s — using heuristic.", exc)

        return self._build_heuristic(
            transcript=transcript,
            speech_transcript=speech_transcript,
            scenes=scenes,
            speakers=speakers,
        )

    def _build_gemini(
        self,
        *,
        transcript: dict[str, Any] | None,
        speech_transcript: dict[str, Any] | None,
        speakers: dict[str, Any] | None,
        scenes: dict[str, Any] | None,
        content_classification: dict[str, Any] | None,
        funny_moments: dict[str, Any] | None,
    ) -> dict[str, Any]:
        from tools.llm.gemini import call_gemini_json

        text = self._extract_text(transcript, speech_transcript)[:4000]
        speaker_roles = (content_classification or {}).get("speaker_roles") or {}
        n_scenes = self._count_scenes(scenes)
        funny_count = len((funny_moments or {}).get("moments") or [])

        prompt = f"""You are an animated podcast visual planner.

Convert this podcast transcript into a scene-by-scene animation plan.

Transcript:
{text}

Speaker roles: {json.dumps(speaker_roles)}
Detected scenes: {n_scenes}
Funny moments count: {funny_count}

For each logical dialogue segment (max 20 scenes), generate:
{{
  "scene_id": "scene_001",
  "speaker": "<speaker role>",
  "dialogue": "<short excerpt>",
  "emotion": "neutral|excited|funny|serious|surprised",
  "environment": "modern podcast studio",
  "camera": "medium shot|close-up|two-shot|wide",
  "animation_style": "subtle motion|talking head|reaction|b-roll overlay",
  "visual_cue": "<brief description of what viewer sees>",
  "duration": <float seconds>
}}

Return JSON:
{{
  "title": "<podcast title or topic>",
  "style": "animated podcast",
  "total_duration": <float>,
  "scenes": [ ... ]
}}"""

        raw = call_gemini_json(prompt)
        if not isinstance(raw, dict) or "scenes" not in raw:
            raise ValueError("Gemini returned invalid animation plan")
        return raw

    def _build_heuristic(
        self,
        *,
        transcript: dict[str, Any] | None,
        speech_transcript: dict[str, Any] | None,
        scenes: dict[str, Any] | None,
        speakers: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Build a simple scene plan from existing scene data + transcript segments."""
        scene_list = []
        raw_scenes = (scenes or {}).get("scenes") or []
        speaker_list = (speakers or {}).get("speakers") or []
        n_spk = len(speaker_list) if isinstance(speaker_list, list) else 1

        # Map transcript segments to scenes
        text = self._extract_text(transcript, speech_transcript)
        sentences = [s.strip() for s in text.replace("\n", " ").split(".") if len(s.strip()) > 20]

        if isinstance(raw_scenes, list) and raw_scenes:
            for i, sc in enumerate(raw_scenes[:20]):
                if not isinstance(sc, dict):
                    continue
                start = float(sc.get("start") or sc.get("start_time") or 0.0)
                end = float(sc.get("end") or sc.get("end_time") or start + 10.0)
                dur = max(end - start, 1.0)
                sentence = sentences[i % len(sentences)] if sentences else "(no dialogue)"
                speaker_idx = i % max(n_spk, 1)
                speaker_id = f"speaker_{speaker_idx}"
                scene_list.append({
                    "scene_id": f"scene_{i+1:03d}",
                    "speaker": speaker_id,
                    "dialogue": sentence[:200],
                    "emotion": "neutral",
                    "environment": "modern podcast studio",
                    "camera": "medium shot" if i % 3 != 0 else "two-shot",
                    "animation_style": "subtle motion",
                    "visual_cue": "Speaker talking to camera in podcast setting",
                    "duration": round(dur, 2),
                })
        else:
            # No scene data — create chunks from transcript sentences
            for i, sentence in enumerate(sentences[:15]):
                scene_list.append({
                    "scene_id": f"scene_{i+1:03d}",
                    "speaker": "speaker_0" if i % 2 == 0 else "speaker_1",
                    "dialogue": sentence[:200],
                    "emotion": "neutral",
                    "environment": "modern podcast studio",
                    "camera": "medium shot",
                    "animation_style": "subtle motion",
                    "visual_cue": "Speaker talking to camera",
                    "duration": 8.0,
                })

        total_duration = sum(s.get("duration", 0.0) for s in scene_list)
        return {
            "title": "Animated Podcast",
            "style": "animated podcast",
            "total_duration": round(total_duration, 2),
            "scenes": scene_list,
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
    def _count_scenes(scenes: dict[str, Any] | None) -> int:
        if not isinstance(scenes, dict):
            return 0
        sc = scenes.get("scenes") or []
        return len(sc) if isinstance(sc, list) else 0

    def _coerce_project(self, project: ProjectMetadata | dict[str, Any]) -> ProjectMetadata:
        if isinstance(project, ProjectMetadata):
            return project
        return ProjectMetadata.model_validate(project)

    def _write(self, project_id: str, root: Path, plan: dict[str, Any]) -> Path:
        try:
            ensure_project_analysis_dir(project_id)
        except Exception:  # noqa: BLE001
            pass
        path = root / "analysis" / "animation_plan.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
        return path
