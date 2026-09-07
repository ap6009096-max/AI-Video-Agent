"""Versioning — manage v1/v2/v3/current output directories per project."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


def _renders_root(project_dir: str | Path) -> Path:
    return Path(project_dir) / "renders"


def _version_dir(project_dir: str | Path, version: int) -> Path:
    return _renders_root(project_dir) / f"v{version}"


def _current_dir(project_dir: str | Path) -> Path:
    return _renders_root(project_dir) / "current"


def _meta_path(project_dir: str | Path) -> Path:
    return _renders_root(project_dir) / "versions.json"


def _load_meta(project_dir: str | Path) -> dict[str, Any]:
    p = _meta_path(project_dir)
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    return {"latest": 0, "versions": []}


def _save_meta(project_dir: str | Path, meta: dict[str, Any]) -> None:
    p = _meta_path(project_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def create_version(project_dir: str | Path) -> int:
    """Archive current/ into vN/ and return the new version number.

    If current/ does not exist this is a no-op and returns 0.
    """
    current = _current_dir(project_dir)
    meta = _load_meta(project_dir)
    if not current.is_dir() or not any(current.iterdir()):
        return meta.get("latest", 0)

    next_v = int(meta.get("latest", 0)) + 1
    dest = _version_dir(project_dir, next_v)
    dest.mkdir(parents=True, exist_ok=True)
    for item in current.iterdir():
        target = dest / item.name
        if item.is_file():
            shutil.copy2(item, target)
        elif item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)

    meta["latest"] = next_v
    versions: list[dict[str, Any]] = meta.get("versions", [])
    versions.append({"version": next_v, "dir": str(dest)})
    meta["versions"] = versions
    _save_meta(project_dir, meta)
    return next_v


def list_versions(project_dir: str | Path) -> list[dict[str, Any]]:
    """Return list of available version dicts: [{version, dir}, ...]."""
    meta = _load_meta(project_dir)
    return meta.get("versions", [])


def get_latest_version(project_dir: str | Path) -> int:
    """Return the latest version number (0 if none archived yet)."""
    return int(_load_meta(project_dir).get("latest", 0))


def rollback(project_dir: str | Path, version: int) -> bool:
    """Restore vN/ into current/.  Returns True on success."""
    src = _version_dir(project_dir, version)
    if not src.is_dir():
        return False
    current = _current_dir(project_dir)
    # Clear current
    if current.is_dir():
        shutil.rmtree(current, ignore_errors=True)
    current.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = current / item.name
        if item.is_file():
            shutil.copy2(item, target)
        elif item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
    return True


def ensure_current_dir(project_dir: str | Path) -> Path:
    """Make sure renders/current/ exists and return its Path."""
    current = _current_dir(project_dir)
    current.mkdir(parents=True, exist_ok=True)
    return current


def get_final_video_path(project_dir: str | Path) -> Path | None:
    """Return the path to final.mp4 in current/, or None if absent."""
    # Check current/ first
    current = _current_dir(project_dir) / "final.mp4"
    if current.is_file():
        return current
    # Fall back to renders/final.mp4 (legacy location)
    legacy = _renders_root(project_dir) / "final.mp4"
    if legacy.is_file():
        return legacy
    return None
