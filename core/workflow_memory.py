"""Filesystem-backed workflow memory store (Prompt 26)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.errors import StorageError, WorkflowError
from core.logging import get_logger
from core.paths import (
    ensure_project_dir,
    get_checkpoints_path,
    get_execution_history_path,
    get_project_dir,
    get_workflow_memory_path,
)
from schemas.base import JobStatus
from schemas.job import ProgressStepStatus
from schemas.memory import WORKFLOW_VERSION, ExecutionHistoryEvent, WorkflowMemory

logger = get_logger(__name__)

# State keys that represent agent pack outputs
AGENT_OUTPUT_KEYS: tuple[str, ...] = (
    "transcript",
    "speech_transcript",
    "analysis",
    "scenes",
    "audio_analysis",
    "speakers",
    "funny_moments",
    "viral_moments",
    "moments",
    "clips",
    "podcast_clips",
    "research_report",
    "supervisor_crew",
    "stories",
    "scripts",
    "country_profile",
    "region_profile",
    "locale_pack",
    "cultural_adaptation",
    "humor_localization",
    "localizations",
    "video_type_pack",
    "visual_style_pack",
    "environment_pack",
    "storyboard_pack",
    "character_pack",
    "camera_pack",
    "director_pack",
    "video_generation_pack",
    "image_pack",
    "broll_pack",
    "voice_pack",
    "avatar_pack",
    "music_pack",
    "captions_pack",
    "reframe_pack",
    "platform_pack",
    "brand_pack",
    "seo_pack",
    "trend_pack",
    "repurpose_pack",
    "calendar_pack",
    "thumbnail_pack",
    "analytics_pack",
    "render_pack",
    "quality_pack",
    "export_pack",
    "source_metadata",
)

# Ordered pipeline node names for clear_from_step (graph order)
PIPELINE_NODE_ORDER: tuple[str, ...] = (
    "input_agent",
    "youtube_ingest",
    "local_video_ingest",
    "script_ingest",
    "step_02_transcript_extracted",
    "video_understanding",
    "scene_detection",
    "audio_analysis",
    "speaker_analysis",
    "moment_detection",
    "funny_moment",
    "viral_moment",
    "smart_clip",
    "podcast",
    "research",
    "supervisor",
    "story",
    "script",
    "country",
    "regional",
    "language",
    "cultural",
    "humor",
    "video_type",
    "visual_style",
    "environment",
    "storyboard",
    "character",
    "camera",
    "director",
    "video_generation",
    "image_generation",
    "b_roll",
    "voice",
    "avatar",
    "music",
    "captions",
    "smart_reframe",
    "platform",
    "brand",
    "seo",
    "trend",
    "repurpose",
    "content_calendar",
    "thumbnail",
    "analytics",
    "render",
    "quality",
    "export",
)

# Map pack keys → relative artifact hints under project dir
_PACK_PATH_HINTS: dict[str, str] = {
    "transcript": "transcript.json",
    "speech_transcript": "transcripts/transcript.json",
    "analysis": "analysis/video_analysis.json",
    "scenes": "analysis/scenes.json",
    "audio_analysis": "analysis/audio_analysis.json",
    "speakers": "analysis/speakers.json",
    "funny_moments": "analysis/funny_moments.json",
    "viral_moments": "analysis/viral_moments.json",
    "moments": "analysis/moments.json",
    "clips": "analysis/clips.json",
    "podcast_clips": "analysis/podcast_clips.json",
    "research_report": "analysis/research_report.json",
    "supervisor_crew": "analysis/supervisor_crew.json",
    "stories": "analysis/stories.json",
    "scripts": "analysis/scripts.json",
    "localizations": "analysis/localizations.json",
    "locale_pack": "analysis/locale_context.json",
    "cultural_adaptation": "analysis/cultural_adaptation.json",
    "humor_localization": "analysis/humor_localization.json",
    "video_type_pack": "analysis/video_type.json",
    "visual_style_pack": "analysis/visual_style.json",
    "environment_pack": "analysis/environment.json",
    "storyboard_pack": "analysis/storyboard_plan.json",
    "character_pack": "analysis/character_plan.json",
    "camera_pack": "analysis/camera_plan.json",
    "director_pack": "analysis/director_plan.json",
    "motion_graphics_pack": "analysis/motion_graphics_plan.json",
    "documentary_pack": "analysis/documentary_plan.json",
    "video_generation_pack": "analysis/video_generation_plan.json",
    "image_pack": "analysis/image_plan.json",
    "broll_pack": "analysis/broll_plan.json",
    "voice_pack": "analysis/voice_plan.json",
    "avatar_pack": "analysis/avatar_plan.json",
    "music_pack": "analysis/music_plan.json",
    "captions_pack": "analysis/captions_plan.json",
    "reframe_pack": "analysis/reframe_plan.json",
    "platform_pack": "analysis/platform_plan.json",
    "brand_pack": "analysis/brand_plan.json",
    "seo_pack": "analysis/seo_plan.json",
    "trend_pack": "analysis/trend_plan.json",
    "repurpose_pack": "analysis/repurpose_plan.json",
    "calendar_pack": "analysis/calendar_plan.json",
    "thumbnail_pack": "analysis/thumbnail_plan.json",
    "analytics_pack": "analysis/analytics_plan.json",
    "render_pack": "analysis/render_plan.json",
    "quality_pack": "analysis/quality_report.json",
    "export_pack": "exports/manifest.json",
    "source_metadata": "source/source_metadata.json",
    "shared_ai_analysis": "analysis/shared_ai_analysis.json",
    "objects_pack": "analysis/objects.json",
    "competitor_pack": "analysis/competitor_pack.json",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_memory(
    project_id: str, output_dir: str | None = None
) -> WorkflowMemory | None:
    path = get_workflow_memory_path(project_id, output_dir)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return WorkflowMemory.model_validate(data)
    except (OSError, json.JSONDecodeError, Exception) as exc:  # noqa: BLE001
        logger.warning("Failed to load memory for %s: %s", project_id, exc)
        return None


def save_memory(memory: WorkflowMemory, output_dir: str | None = None) -> Path:
    project_id = memory.project_id or memory.thread_id
    if not project_id:
        raise StorageError("Cannot save memory without project_id")
    ensure_project_dir(project_id, output_dir)
    memory.updated_at = _utc_now_iso()
    if not memory.thread_id:
        memory.thread_id = project_id
    path = get_workflow_memory_path(project_id, output_dir)
    try:
        path.write_text(
            json.dumps(memory.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        raise StorageError(f"Failed to write memory.json: {exc}") from exc
    return path


def append_history(
    project_id: str,
    event: ExecutionHistoryEvent | dict[str, Any],
    output_dir: str | None = None,
) -> Path:
    ensure_project_dir(project_id, output_dir)
    path = get_execution_history_path(project_id, output_dir)
    if isinstance(event, dict):
        event = ExecutionHistoryEvent.model_validate(event)
    try:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event.model_dump(mode="json")) + "\n")
    except OSError as exc:
        raise StorageError(f"Failed to append execution history: {exc}") from exc
    return path


def read_history(
    project_id: str, output_dir: str | None = None, *, limit: int = 500
) -> list[ExecutionHistoryEvent]:
    path = get_execution_history_path(project_id, output_dir)
    if not path.is_file():
        return []
    events: list[ExecutionHistoryEvent] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        for line in lines[-limit:]:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(ExecutionHistoryEvent.model_validate(json.loads(line)))
            except Exception:  # noqa: BLE001
                continue
    except OSError:
        return []
    return events


def new_memory(
    project_id: str,
    *,
    job: dict[str, Any] | None = None,
    project_dir: str = "",
) -> WorkflowMemory:
    return WorkflowMemory(
        project_id=project_id,
        workflow_version=WORKFLOW_VERSION,
        thread_id=project_id,
        status=JobStatus.PENDING.value,
        job=dict(job or {}),
        project_dir=project_dir or str(get_project_dir(project_id)),
    )


def assert_compatible_version(memory: WorkflowMemory) -> None:
    if memory.workflow_version != WORKFLOW_VERSION:
        raise WorkflowError(
            f"Workflow version mismatch: memory={memory.workflow_version!r} "
            f"current={WORKFLOW_VERSION!r}. Force a full rerun."
        )


def _summarize_output(key: str, value: Any, project_dir: str | None) -> Any:
    """Prefer artifact path when available; else a small summary."""
    if value is None:
        return None
    if project_dir:
        hint = _PACK_PATH_HINTS.get(key)
        if hint:
            candidate = Path(project_dir) / hint
            if candidate.is_file():
                return {"path": str(candidate), "present": True}
    if isinstance(value, dict):
        summary: dict[str, Any] = {"keys": list(value.keys())[:12]}
        for path_key in ("path", "export_path", "output_path", "manifest_path"):
            if value.get(path_key):
                summary[path_key] = value.get(path_key)
        plan = value.get("plan")
        if isinstance(plan, dict):
            summary["skipped"] = plan.get("skipped")
            summary["encoded"] = plan.get("encoded")
        return summary
    return {"type": type(value).__name__}


def update_from_workflow_state(
    state: dict[str, Any],
    *,
    last_node: str = "",
    output_dir: str | None = None,
) -> WorkflowMemory:
    """Derive and persist WorkflowMemory from a live WorkflowState snapshot."""
    project = state.get("project") or {}
    job = state.get("job") or {}
    project_id = (
        str(project.get("project_id") or job.get("job_id") or "").strip()
    )
    if not project_id:
        # Cannot persist yet (pre-input)
        return WorkflowMemory()

    existing = load_memory(project_id, output_dir) or new_memory(
        project_id, job=job, project_dir=str(state.get("project_dir") or "")
    )
    existing.workflow_version = WORKFLOW_VERSION
    existing.project_id = project_id
    existing.thread_id = project_id
    existing.job = dict(job)
    existing.project_dir = str(state.get("project_dir") or existing.project_dir)
    existing.status = str(state.get("status") or existing.status)
    existing.error = state.get("error")

    steps = state.get("steps") or []
    completed: list[str] = []
    failed: list[str] = []
    current_label = ""
    for step in steps:
        if not isinstance(step, dict):
            continue
        label = str(step.get("label") or step.get("id") or "")
        status = step.get("status")
        if status == ProgressStepStatus.COMPLETED.value:
            if label and label not in completed:
                completed.append(label)
        elif status == ProgressStepStatus.FAILED.value:
            if label and label not in failed:
                failed.append(label)
        elif status == ProgressStepStatus.RUNNING.value:
            current_label = label

    existing.completed_steps = completed
    existing.failed_steps = failed
    if not failed and existing.status == JobStatus.FAILED.value:
        label = current_label or last_node or existing.current_step
        if label and label not in existing.failed_steps:
            existing.failed_steps = [label]
    if current_label:
        existing.current_step = current_label
    elif last_node:
        existing.current_step = last_node

    if last_node:
        existing.last_node = last_node
        existing.timestamps[last_node] = _utc_now_iso()
        try:
            from schemas.creator_os import stage_for_node

            stage = stage_for_node(last_node)
            if stage:
                existing.last_stage = stage
        except Exception:  # noqa: BLE001
            pass

    project_dir = existing.project_dir
    for key in AGENT_OUTPUT_KEYS:
        if key in state and state.get(key) is not None:
            existing.agent_outputs[key] = _summarize_output(
                key, state.get(key), project_dir
            )

    # Index current_step int as well under timestamps meta
    try:
        idx = int(state.get("current_step", -1))
        existing.timestamps["_current_step_index"] = str(idx)
    except (TypeError, ValueError):
        pass

    save_memory(existing, output_dir)
    return existing


def clear_from_step(memory: WorkflowMemory, step: str) -> WorkflowMemory:
    """Drop completed/failed/outputs/timestamps from ``step`` onward (inclusive)."""
    step = (step or "").strip()
    if not step:
        return memory

    # Resolve index in PIPELINE_NODE_ORDER; also allow UI labels
    idx = None
    if step in PIPELINE_NODE_ORDER:
        idx = PIPELINE_NODE_ORDER.index(step)
    else:
        # Try match against completed_steps labels — clear from first label match
        # by clearing all completed after and including that label
        if step in memory.completed_steps:
            # Keep completed before this label
            keep = []
            clearing = False
            for label in memory.completed_steps:
                if label == step or clearing:
                    clearing = True
                    continue
                keep.append(label)
            memory.completed_steps = keep
            memory.failed_steps = [s for s in memory.failed_steps if s != step]
            # Clear agent outputs that typically appear at/after that UI stage — best effort:
            # clear nothing pack-specific when only label known beyond label lists
            memory.current_step = step
            memory.status = JobStatus.RUNNING.value
            memory.error = None
            memory.last_node = step
            return memory

    if idx is None:
        # Unknown step — treat as node name string removal only
        memory.completed_steps = [s for s in memory.completed_steps if s != step]
        memory.failed_steps = [s for s in memory.failed_steps if s != step]
        memory.timestamps.pop(step, None)
        memory.agent_outputs.pop(step, None)
        memory.current_step = step
        memory.status = JobStatus.RUNNING.value
        memory.error = None
        return memory

    drop_nodes = set(PIPELINE_NODE_ORDER[idx:])
    memory.timestamps = {
        k: v for k, v in memory.timestamps.items() if k not in drop_nodes
    }
    # Map nodes → packs roughly for clearing outputs
    node_to_packs: dict[str, tuple[str, ...]] = {
        "step_02_transcript_extracted": ("transcript", "speech_transcript"),
        "video_understanding": ("analysis",),
        "scene_detection": ("scenes",),
        "audio_analysis": ("audio_analysis",),
        "speaker_analysis": ("speakers",),
        "moment_detection": ("moments",),
        "funny_moment": ("funny_moments",),
        "viral_moment": ("viral_moments",),
        "smart_clip": ("clips",),
        "podcast": ("podcast_clips",),
        "research": ("research_report",),
        "supervisor": ("supervisor_crew",),
        "story": ("stories",),
        "script": ("scripts",),
        "country": ("country_profile",),
        "regional": ("region_profile", "locale_pack"),
        "language": ("localizations",),
        "cultural": ("cultural_adaptation",),
        "humor": ("humor_localization",),
        "video_type": ("video_type_pack",),
        "visual_style": ("visual_style_pack",),
        "environment": ("environment_pack",),
        "storyboard": ("storyboard_pack",),
        "character": ("character_pack",),
        "camera": ("camera_pack",),
        "director": ("director_pack",),
        "video_generation": ("video_generation_pack",),
        "image_generation": ("image_pack",),
        "b_roll": ("broll_pack",),
        "voice": ("voice_pack",),
        "avatar": ("avatar_pack",),
        "music": ("music_pack",),
        "captions": ("captions_pack",),
        "smart_reframe": ("reframe_pack",),
        "platform": ("platform_pack",),
        "brand": ("brand_pack",),
        "seo": ("seo_pack",),
        "trend": ("trend_pack",),
        "repurpose": ("repurpose_pack",),
        "content_calendar": ("calendar_pack",),
        "thumbnail": ("thumbnail_pack",),
        "analytics": ("analytics_pack",),
        "render": ("render_pack",),
        "quality": ("quality_pack",),
        "export": ("export_pack",),
        "youtube_ingest": ("source_metadata",),
        "local_video_ingest": ("source_metadata",),
        "script_ingest": ("transcript", "source_metadata"),
    }
    drop_packs: set[str] = set()
    for node in drop_nodes:
        drop_packs.update(node_to_packs.get(node, ()))
    memory.agent_outputs = {
        k: v for k, v in memory.agent_outputs.items() if k not in drop_packs
    }
    # completed_steps are UI labels — keep those before the cut heuristically:
    # if step is a node name, leave UI labels as-is except clear failed
    memory.failed_steps = [s for s in memory.failed_steps if s not in drop_nodes]
    memory.completed_steps = [
        s for s in memory.completed_steps if s not in drop_nodes
    ]
    memory.current_step = step
    memory.last_node = step
    memory.status = JobStatus.RUNNING.value
    memory.error = None
    return memory


def list_resumable_projects(output_dir: str | None = None) -> list[WorkflowMemory]:
    """Return incomplete project memories newest-first."""
    from core.paths import ensure_projects_dir

    root = ensure_projects_dir(output_dir)
    found: list[WorkflowMemory] = []
    if not root.is_dir():
        return found
    for child in root.iterdir():
        if not child.is_dir():
            continue
        mem = load_memory(child.name, output_dir)
        if mem is None:
            continue
        if mem.status in {
            JobStatus.COMPLETED.value,
        }:
            continue
        found.append(mem)
    found.sort(key=lambda m: m.updated_at or m.created_at, reverse=True)
    return found


def get_checkpointer(project_id: str, output_dir: str | None = None):
    """Return a SqliteSaver bound to the project checkpoints file.

    Caller owns the connection lifetime for the duration of the run.
    """
    import sqlite3

    from langgraph.checkpoint.sqlite import SqliteSaver

    ensure_project_dir(project_id, output_dir)
    db_path = get_checkpoints_path(project_id, output_dir)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    return saver, conn
