"""Rehydrate WorkflowState packs from on-disk agent artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.logging import get_logger
from core.workflow_memory import _PACK_PATH_HINTS
from core.errors import WorkflowError
from schemas.project import ProjectMetadata

logger = get_logger(__name__)


def load_pack_json(path: Path) -> Any | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read pack %s: %s", path, exc)
        return None


def _rehydrate_project_metadata(state: dict[str, Any], root: Path) -> dict[str, Any] | None:
    """Restore project metadata before downstream nodes validate it."""
    if state.get("project"):
        return state["project"]

    path = root / "project.json"
    data = load_pack_json(path)
    if data is None:
        if not path.is_file():
            return None
        data = {}
    if not isinstance(data, dict):
        raise WorkflowError(f"Invalid project metadata in {path}")

    # Older/partial metadata can be recovered from the validated workflow job.
    if not data.get("source_type"):
        job = state.get("job") or {}
        source_type = job.get("source_type")
        if source_type:
            data["source_type"] = source_type
            data.setdefault("project_id", job.get("job_id"))
            data.setdefault("youtube_url", job.get("youtube_url") or "")
            data.setdefault("source_path", job.get("upload_path") or "")
            data.setdefault("raw_text", job.get("script_text") or "")

    try:
        return ProjectMetadata.model_validate(data).model_dump(mode="json")
    except Exception as exc:  # noqa: BLE001 - expose a workflow-level diagnosis
        raise WorkflowError(
            f"Unable to restore project metadata from {path}: source_type is missing "
            "or invalid. Please start a new job with a YouTube URL or supported media source."
        ) from exc


def rehydrate_state_from_disk(
    state: dict[str, Any],
    project_dir: str | Path,
    *,
    only_keys: set[str] | None = None,
) -> dict[str, Any]:
    """Fill missing agent pack keys from project artifact files."""
    root = Path(project_dir)
    out = dict(state)
    out.setdefault("project_dir", str(root))
    project = _rehydrate_project_metadata(out, root)
    if project is not None:
        out["project"] = project
    try:
        from schemas.project_refs import refs_from_project_dir

        for k, v in refs_from_project_dir(str(root)).items():
            out.setdefault(k, v)
    except Exception:  # noqa: BLE001
        pass
    for key, rel in _PACK_PATH_HINTS.items():
        if only_keys is not None and key not in only_keys:
            continue
        if out.get(key) is not None:
            continue
        data = load_pack_json(root / rel)
        if data is not None:
            out[key] = data
    return out
