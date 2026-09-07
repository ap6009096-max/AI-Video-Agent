"""Dual-write project layout aliases and aggregators (PROMPT 25)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

REQUIRED_DIRS = (
    "source",
    "transcripts",
    "analysis",
    "clips",
    "audio",
    "subtitles",
    "thumbnails",
    "images",
    "final",
    "captions",
    "renders",
    "exports",
    "cache",
    "logs",
)


def ensure_project_layout(root: Path) -> dict[str, Path]:
    """Create required project subfolders; return path map."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}
    for name in REQUIRED_DIRS:
        p = root / name
        p.mkdir(parents=True, exist_ok=True)
        out[name] = p
    return out


def _copy_file(src: Path, dst: Path) -> str:
    try:
        if not src.is_file():
            return ""
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.resolve() != dst.resolve():
            shutil.copy2(src, dst)
        return str(dst) if dst.is_file() else ""
    except OSError as exc:
        logger.warning("layout copy failed %s -> %s: %s", src, dst, exc)
        return ""


def _read_json(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_json(path: Path, payload: Any) -> str:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return str(path)
    except OSError as exc:
        logger.warning("layout write failed %s: %s", path, exc)
        return ""


def build_localization_rollup(root: Path, state: dict[str, Any] | None = None) -> dict[str, Any]:
    state = state or {}
    return {
        "locale_pack": state.get("locale_pack")
        or _read_json(root / "analysis" / "locale_context.json"),
        "localizations": state.get("localizations")
        or _read_json(root / "analysis" / "localizations.json"),
        "cultural_adaptation": state.get("cultural_adaptation")
        or _read_json(root / "analysis" / "cultural_adaptation.json"),
        "humor_localization": state.get("humor_localization")
        or _read_json(root / "analysis" / "humor_localization.json"),
        "country_profile": state.get("country_profile"),
        "region_profile": state.get("region_profile"),
    }


def build_video_plan_rollup(root: Path, state: dict[str, Any] | None = None) -> dict[str, Any]:
    state = state or {}
    analysis = root / "analysis"

    def pack(key: str, filename: str) -> Any:
        return state.get(key) or _read_json(analysis / filename)

    return {
        "video_type": pack("video_type_pack", "video_type.json"),
        "visual_style": pack("visual_style_pack", "visual_style.json"),
        "environment": pack("environment_pack", "environment.json"),
        "broll": pack("broll_pack", "broll_plan.json"),
        "voice": pack("voice_pack", "voice_plan.json"),
        "music": pack("music_pack", "music_plan.json"),
        "captions": pack("captions_pack", "captions_plan.json"),
        "reframe": pack("reframe_pack", "reframe_plan.json"),
        "platform": pack("platform_pack", "platform_plan.json"),
        "render": pack("render_pack", "render_plan.json"),
    }


def finalize_project_layout(
    root: str | Path,
    *,
    state: dict[str, Any] | None = None,
    captions_pack: dict[str, Any] | None = None,
    render_pack: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Dual-write aliases, populate deliverable folders, return output_files."""
    root = Path(root)
    state = dict(state or {})
    dirs = ensure_project_layout(root)
    analysis = dirs["analysis"]
    output_files: dict[str, Any] = {"aliases": {}, "folders": {}}

    # Root JSON aliases
    alias_map = {
        "scenes.json": analysis / "scenes.json",
        "analysis.json": analysis / "video_analysis.json",
        "moments.json": analysis / "moments.json",
        "clips.json": analysis / "clips.json",
        "quality_report.json": analysis / "quality_report.json",
    }
    for name, src in alias_map.items():
        path = _copy_file(src, root / name)
        if path:
            output_files["aliases"][name] = path

    # transcript.json at root if missing but present under transcripts/
    root_tx = root / "transcript.json"
    if not root_tx.is_file():
        for cand in (
            root / "transcripts" / "transcript.json",
            analysis / "transcript.json",
        ):
            if cand.is_file():
                _copy_file(cand, root_tx)
                break
    if root_tx.is_file():
        output_files["aliases"]["transcript.json"] = str(root_tx)

    localization = build_localization_rollup(root, state)
    loc_path = _write_json(root / "localization.json", localization)
    if loc_path:
        output_files["aliases"]["localization.json"] = loc_path

    video_plan = build_video_plan_rollup(root, state)
    vp_path = _write_json(root / "video_plan.json", video_plan)
    if vp_path:
        output_files["aliases"]["video_plan.json"] = vp_path

    # Subtitles from captions pack / captions dir
    cap = captions_pack or state.get("captions_pack") or {}
    sub_paths: list[str] = []
    for key in ("srt_path", "vtt_path", "ass_path"):
        p = str(cap.get(key) or "").strip()
        if p and Path(p).is_file():
            dest = dirs["subtitles"] / Path(p).name
            copied = _copy_file(Path(p), dest)
            if copied:
                sub_paths.append(copied)
    captions_dir = root / "captions"
    if captions_dir.is_dir():
        for ext in ("*.srt", "*.vtt", "*.ass"):
            for f in captions_dir.glob(ext):
                copied = _copy_file(f, dirs["subtitles"] / f.name)
                if copied and copied not in sub_paths:
                    sub_paths.append(copied)
    output_files["folders"]["subtitles"] = sub_paths

    # Thumbnail
    thumbs: list[str] = []
    rp = render_pack or state.get("render_pack") or {}
    plan = rp.get("plan") if isinstance(rp, dict) else {}
    if isinstance(plan, dict):
        tp = str(plan.get("thumbnail_path") or "").strip()
        if tp and Path(tp).is_file():
            copied = _copy_file(Path(tp), dirs["thumbnails"] / Path(tp).name)
            if copied:
                thumbs.append(copied)
    for cand in (
        root / "renders" / "thumbnail.jpg",
        root / "exports" / "thumbnail.jpg",
    ):
        if cand.is_file():
            copied = _copy_file(cand, dirs["thumbnails"] / cand.name)
            if copied and copied not in thumbs:
                thumbs.append(copied)
    output_files["folders"]["thumbnails"] = thumbs

    # Final video
    finals: list[str] = []
    if isinstance(plan, dict):
        op = str(plan.get("output_path") or "").strip()
        if op and Path(op).is_file():
            copied = _copy_file(Path(op), dirs["final"] / Path(op).name)
            if copied:
                finals.append(copied)
    for cand in (
        root / "renders" / "final.mp4",
        root / "exports" / "final.mp4",
    ):
        if cand.is_file():
            copied = _copy_file(cand, dirs["final"] / cand.name)
            if copied and copied not in finals:
                finals.append(copied)
    output_files["folders"]["final"] = finals

    # Multi Shorts MP4s
    shorts_files: list[str] = []
    shorts_dir = root / "renders" / "shorts"
    if shorts_dir.is_dir():
        for mp4 in sorted(shorts_dir.glob("short_*.mp4")):
            if mp4.is_file():
                copied = _copy_file(mp4, dirs["final"] / mp4.name)
                if copied:
                    shorts_files.append(copied)
                else:
                    shorts_files.append(str(mp4.resolve()))
    if isinstance(plan, dict):
        for sp in plan.get("short_paths") or []:
            p = Path(str(sp))
            if p.is_file():
                copied = _copy_file(p, dirs["final"] / p.name)
                path_s = copied or str(p.resolve())
                if path_s not in shorts_files:
                    shorts_files.append(path_s)
    if shorts_files:
        output_files["folders"]["shorts"] = shorts_files
        # Also list under clips deliverable folder
        clip_short_copies: list[str] = []
        for sp in shorts_files:
            src = Path(sp)
            if src.is_file():
                copied = _copy_file(src, dirs["clips"] / src.name)
                if copied:
                    clip_short_copies.append(copied)
        if clip_short_copies:
            existing = list(output_files.get("folders", {}).get("clips") or [])
            output_files.setdefault("folders", {})["clips"] = (
                existing + clip_short_copies
            )

    # Clips JSON note (media cuts optional)
    clips_json = analysis / "clips.json"
    clip_files: list[str] = list(output_files.get("folders", {}).get("clips") or [])
    if clips_json.is_file():
        copied = _copy_file(clips_json, dirs["clips"] / "clips.json")
        if copied and copied not in clip_files:
            clip_files.append(copied)
    podcast_json = analysis / "podcast_clips.json"
    if podcast_json.is_file():
        copied = _copy_file(podcast_json, dirs["clips"] / "podcast_clips.json")
        if copied and copied not in clip_files:
            clip_files.append(copied)
    if clip_files:
        output_files["folders"]["clips"] = clip_files

    # Audio folder placeholder note when no stems
    audio_note = dirs["audio"] / "README.txt"
    if not any(dirs["audio"].iterdir()):
        try:
            audio_note.write_text(
                "Audio stems are copied here when extracted/generated.\n",
                encoding="utf-8",
            )
        except OSError:
            pass
    output_files["folders"]["audio"] = [
        str(p) for p in dirs["audio"].iterdir() if p.is_file()
    ]

    if (root / "project.json").is_file():
        output_files["aliases"]["project.json"] = str(root / "project.json")

    return output_files
