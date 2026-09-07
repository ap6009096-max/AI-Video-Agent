"""Supervisor crew helpers — shared worker runners + routing for LangGraph."""

from __future__ import annotations

from typing import Any

from agents.caption_agent import CaptionAgent
from agents.director_agent import DirectorAgent
from agents.research_agent import ResearchAgent
from agents.script_agent import ScriptAgent
from agents.seo_agent import SeoAgent
from agents.story_agent import StoryAgent
from agents.supervisor_agent import SupervisorAgent, pack_looks_complete
from agents.thumbnail_agent import ThumbnailAgent
from agents.video_generation_agent import VideoGenerationAgent
from core.errors import SupervisorAgentError
from core.logging import get_logger
from schemas.base import JobStatus
from schemas.project import ProjectMetadata
from schemas.supervisor import CREW_WORKER_ORDER, CrewReport

logger = get_logger(__name__)

CREW_WORKER_NODES: tuple[str, ...] = CREW_WORKER_ORDER


def force_crew_features(features: dict[str, Any] | None) -> dict[str, Any]:
    """Enable packs the crew must produce regardless of UI toggles."""
    f = dict(features or {})
    f["research"] = True
    f["director"] = True
    f["video_generation"] = True
    f["captions"] = True
    f["thumbnail"] = True
    f["seo"] = True
    f["supervisor_crew"] = True
    return f


def parse_crew_step(messages: list[str] | None) -> int:
    for line in reversed(messages or []):
        if "crew_step=" in line:
            try:
                return int(str(line).rsplit("crew_step=", 1)[-1].strip())
            except ValueError:
                continue
    return 0


def run_supervisor_turn(state: dict[str, Any]) -> dict[str, Any]:
    """Execute one supervisor decision turn and persist crew report."""
    project_raw = state.get("project") or {}
    if not project_raw:
        return {
            "status": JobStatus.FAILED.value,
            "error": "Missing project for supervisor",
            "next_agent": "FINISH",
        }
    try:
        project = ProjectMetadata.model_validate(project_raw)
        result = SupervisorAgent().run(
            project,
            project_dir=state.get("project_dir"),
            state=dict(state),
            persist=True,
        )
    except SupervisorAgentError as exc:
        return {
            "status": JobStatus.FAILED.value,
            "error": str(exc),
            "next_agent": "FINISH",
            "messages": list(state.get("messages") or [])
            + [f"[supervisor] Failed: {exc}"],
        }

    report = result.supervisor_crew
    decision = report.decisions[-1] if report.decisions else None
    next_agent = decision.next_agent if decision else "FINISH"
    crew_step = parse_crew_step(result.messages) or int(state.get("crew_step") or 0) + 1
    messages = list(state.get("messages") or [])
    messages.extend(result.messages)
    out = {
        **result.to_state_dict(),
        "next_agent": next_agent,
        "crew_step": crew_step,
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }
    return out


def route_supervisor_next(state: dict[str, Any]) -> str:
    """Map supervisor decision to a worker node name or FINISH."""
    if state.get("status") == JobStatus.FAILED.value or state.get("error"):
        return "crew_failed"
    nxt = str(state.get("next_agent") or "FINISH").strip()
    if nxt == "FINISH" or nxt not in CREW_WORKER_NODES:
        return "FINISH"
    return nxt


def _merge_worker_ok(
    state: dict[str, Any],
    *,
    worker: str,
    pack_update: dict[str, Any],
    agent_messages: list[str],
    ok: bool,
    notes: str = "",
) -> dict[str, Any]:
    messages = list(state.get("messages") or [])
    direction = "ok" if ok else "failed"
    messages.append(f"[{worker} → supervisor] {direction}: {notes or worker}")
    messages.extend(agent_messages)

    report_raw = state.get("supervisor_crew") or {}
    try:
        report = CrewReport.model_validate(report_raw) if report_raw else CrewReport(
            project_id=(state.get("project") or {}).get("project_id") or "unknown"
        )
    except Exception:  # noqa: BLE001
        report = CrewReport(
            project_id=(state.get("project") or {}).get("project_id") or "unknown"
        )

    agent = SupervisorAgent()
    report = agent.mark_worker_result(
        report,
        worker=worker,
        ok=ok,
        notes=notes,
        retry_counts=dict(state.get("crew_retry_counts") or report.retry_counts),
    )
    # Persist updated report
    project_raw = state.get("project") or {}
    project_id = project_raw.get("project_id") if isinstance(project_raw, dict) else "unknown"
    project_dir = state.get("project_dir")
    if project_dir and project_id:
        try:
            from pathlib import Path
            import json

            path = Path(project_dir) / "analysis" / "supervisor_crew.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            logger.exception("Failed to persist supervisor_crew.json after %s", worker)

    out: dict[str, Any] = {
        **pack_update,
        "supervisor_crew": report.model_dump(mode="json"),
        "delegation_log": [e.model_dump(mode="json") for e in report.delegation_log],
        "task_board": [t.model_dump(mode="json") for t in report.task_board],
        "crew_retry_counts": dict(report.retry_counts),
        "messages": messages,
        "status": JobStatus.RUNNING.value,
        "error": None,
    }
    return out


def run_crew_research(state: dict[str, Any]) -> dict[str, Any]:
    project = state.get("project")
    job = state.get("job") or {}
    features = force_crew_features(job.get("features"))
    try:
        result = ResearchAgent().run(
            project,
            project_dir=state.get("project_dir"),
            features=features,
            config=job.get("config"),
            transcript=state.get("transcript"),
            speech_transcript=state.get("speech_transcript"),
            analysis=state.get("analysis"),
            source_metadata=state.get("source_metadata"),
            source_type=job.get("source_type"),
            youtube_url=job.get("youtube_url"),
        )
        update = result.to_state_dict()
        ok = pack_looks_complete("research", {**state, **update})
        return _merge_worker_ok(
            state,
            worker="research",
            pack_update=update,
            agent_messages=result.messages,
            ok=ok,
            notes=f"claims={len((update.get('research_report') or {}).get('claims') or [])}",
        )
    except Exception as exc:  # noqa: BLE001
        return _merge_worker_ok(
            state,
            worker="research",
            pack_update={"research_report": state.get("research_report")},
            agent_messages=[],
            ok=False,
            notes=str(exc),
        )


def run_crew_story(state: dict[str, Any]) -> dict[str, Any]:
    project = state.get("project")
    job = state.get("job") or {}
    try:
        result = StoryAgent().run(
            project,
            project_dir=state.get("project_dir"),
            clips=state.get("clips"),
            transcript=state.get("transcript"),
            speech_transcript=state.get("speech_transcript"),
            config=job.get("config"),
            video_type_pack=state.get("video_type_pack"),
            visual_style_pack=state.get("visual_style_pack"),
            environment_pack=state.get("environment_pack"),
            research_report=state.get("research_report"),
        )
        update = result.to_state_dict()
        ok = pack_looks_complete("story", {**state, **update})
        return _merge_worker_ok(
            state,
            worker="story",
            pack_update=update,
            agent_messages=result.messages,
            ok=ok,
            notes=f"stories={len((update.get('stories') or {}).get('stories') or [])}",
        )
    except Exception as exc:  # noqa: BLE001
        return _merge_worker_ok(
            state,
            worker="story",
            pack_update={},
            agent_messages=[],
            ok=False,
            notes=str(exc),
        )


def run_crew_script(state: dict[str, Any]) -> dict[str, Any]:
    project = state.get("project")
    job = state.get("job") or {}
    try:
        result = ScriptAgent().run(
            project,
            project_dir=state.get("project_dir"),
            clips=state.get("clips"),
            stories=state.get("stories"),
            transcript=state.get("transcript"),
            speech_transcript=state.get("speech_transcript"),
            config=job.get("config"),
            video_type_pack=state.get("video_type_pack"),
            visual_style_pack=state.get("visual_style_pack"),
            environment_pack=state.get("environment_pack"),
            research_report=state.get("research_report"),
        )
        update = result.to_state_dict()
        ok = pack_looks_complete("script", {**state, **update})
        return _merge_worker_ok(
            state,
            worker="script",
            pack_update=update,
            agent_messages=result.messages,
            ok=ok,
            notes=f"scripts={len((update.get('scripts') or {}).get('scripts') or [])}",
        )
    except Exception as exc:  # noqa: BLE001
        return _merge_worker_ok(
            state,
            worker="script",
            pack_update={},
            agent_messages=[],
            ok=False,
            notes=str(exc),
        )


def run_crew_director(state: dict[str, Any]) -> dict[str, Any]:
    project = state.get("project")
    job = state.get("job") or {}
    features = force_crew_features(job.get("features"))
    try:
        result = DirectorAgent().run(
            project,
            project_dir=state.get("project_dir"),
            config=job.get("config"),
            features=features,
            script_pack=state.get("scripts"),
            storyboard_pack=state.get("storyboard_pack"),
            stories=state.get("stories"),
            visual_style_pack=state.get("visual_style_pack"),
            environment_pack=state.get("environment_pack"),
            character_pack=state.get("character_pack"),
            camera_pack=state.get("camera_pack"),
        )
        update = result.to_state_dict()
        ok = pack_looks_complete("director", {**state, **update})
        return _merge_worker_ok(
            state,
            worker="director",
            pack_update=update,
            agent_messages=result.messages,
            ok=ok,
            notes="director_pack",
        )
    except Exception as exc:  # noqa: BLE001
        return _merge_worker_ok(
            state,
            worker="director",
            pack_update={},
            agent_messages=[],
            ok=False,
            notes=str(exc),
        )


def run_crew_video_generation(state: dict[str, Any]) -> dict[str, Any]:
    project = state.get("project")
    job = state.get("job") or {}
    features = force_crew_features(job.get("features"))
    try:
        result = VideoGenerationAgent().run(
            project,
            project_dir=state.get("project_dir"),
            config=job.get("config"),
            features=features,
            script_pack=state.get("scripts"),
            storyboard_pack=state.get("storyboard_pack"),
            visual_style_pack=state.get("visual_style_pack"),
            environment_pack=state.get("environment_pack"),
            director_pack=state.get("director_pack"),
            character_pack=state.get("character_pack"),
            camera_pack=state.get("camera_pack"),
            motion_graphics_pack=state.get("motion_graphics_pack"),
            documentary_pack=state.get("documentary_pack"),
        )
        update = result.to_state_dict()
        ok = pack_looks_complete("video_generation", {**state, **update})
        return _merge_worker_ok(
            state,
            worker="video_generation",
            pack_update=update,
            agent_messages=result.messages,
            ok=ok,
            notes="video_generation_pack",
        )
    except Exception as exc:  # noqa: BLE001
        return _merge_worker_ok(
            state,
            worker="video_generation",
            pack_update={},
            agent_messages=[],
            ok=False,
            notes=str(exc),
        )


def run_crew_captions(state: dict[str, Any]) -> dict[str, Any]:
    project = state.get("project")
    job = state.get("job") or {}
    features = force_crew_features(job.get("features"))
    try:
        result = CaptionAgent().run(
            project,
            project_dir=state.get("project_dir"),
            config=job.get("config"),
            features=features,
            speech_transcript=state.get("speech_transcript"),
            transcript=state.get("transcript"),
            localizations=state.get("localizations"),
            locale_pack=state.get("locale_pack"),
            source_metadata=state.get("source_metadata"),
        )
        update = result.to_state_dict()
        ok = pack_looks_complete("captions", {**state, **update})
        return _merge_worker_ok(
            state,
            worker="captions",
            pack_update=update,
            agent_messages=result.messages,
            ok=ok,
            notes="captions_pack",
        )
    except Exception as exc:  # noqa: BLE001
        return _merge_worker_ok(
            state,
            worker="captions",
            pack_update={},
            agent_messages=[],
            ok=False,
            notes=str(exc),
        )


def run_crew_thumbnail(state: dict[str, Any]) -> dict[str, Any]:
    project = state.get("project")
    job = state.get("job") or {}
    features = force_crew_features(job.get("features"))
    try:
        result = ThumbnailAgent().run(
            project,
            project_dir=state.get("project_dir"),
            config=job.get("config"),
            features=features,
            script_pack=state.get("scripts"),
            platform_pack=state.get("platform_pack"),
            viral_pack=state.get("viral_moments"),
            seo_pack=state.get("seo_pack"),
            trend_pack=state.get("trend_pack"),
        )
        update = result.to_state_dict()
        ok = pack_looks_complete("thumbnail", {**state, **update})
        return _merge_worker_ok(
            state,
            worker="thumbnail",
            pack_update=update,
            agent_messages=result.messages,
            ok=ok,
            notes="thumbnail_pack",
        )
    except Exception as exc:  # noqa: BLE001
        return _merge_worker_ok(
            state,
            worker="thumbnail",
            pack_update={},
            agent_messages=[],
            ok=False,
            notes=str(exc),
        )


def run_crew_seo(state: dict[str, Any]) -> dict[str, Any]:
    project = state.get("project")
    job = state.get("job") or {}
    features = force_crew_features(job.get("features"))
    try:
        result = SeoAgent().run(
            project,
            project_dir=state.get("project_dir"),
            config=job.get("config"),
            features=features,
            script_pack=state.get("scripts"),
            platform_pack=state.get("platform_pack"),
        )
        update = result.to_state_dict()
        ok = pack_looks_complete("seo", {**state, **update})
        return _merge_worker_ok(
            state,
            worker="seo",
            pack_update=update,
            agent_messages=result.messages,
            ok=ok,
            notes="seo_pack",
        )
    except Exception as exc:  # noqa: BLE001
        return _merge_worker_ok(
            state,
            worker="seo",
            pack_update={},
            agent_messages=[],
            ok=False,
            notes=str(exc),
        )


WORKER_RUNNERS: dict[str, Any] = {
    "research": run_crew_research,
    "story": run_crew_story,
    "script": run_crew_script,
    "director": run_crew_director,
    "video_generation": run_crew_video_generation,
    "captions": run_crew_captions,
    "thumbnail": run_crew_thumbnail,
    "seo": run_crew_seo,
}
