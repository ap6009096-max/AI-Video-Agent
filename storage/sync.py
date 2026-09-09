"""Sync local project artifacts to/from durable object storage."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from core.logging import get_logger
from storage import get_object_storage, upload_project_file
from storage.refs import MediaRef

logger = get_logger(__name__)

# category → relative paths under project_dir to sync after render/export
DEFAULT_ARTIFACT_GLOBS: dict[str, tuple[str, ...]] = {
    "final": ("final/final.mp4", "renders/final.mp4", "renders/current/final.mp4"),
    "captions": ("captions/captions.srt", "captions/captions.vtt", "subtitles/captions.srt"),
    "thumbnails": ("renders/thumbnail.jpg", "thumbnails/thumbnail.jpg"),
    "shorts": (),  # handled via directory scan
    "exports": ("exports/manifest.json", "exports/output_manifest.json"),
    "audio": ("audio/final_voice.wav",),
}


def persist_source_media(
    *,
    project_id: str,
    local_path: str | Path,
    source_type: str = "",
    source_url: str = "",
    original_filename: str | None = None,
    mime_type: str = "",
) -> MediaRef:
    """Upload source media to durable storage and return a MediaRef."""
    path = Path(local_path)
    storage = get_object_storage()
    logger.info("STORAGE_UPLOAD_STARTED category=source project_id=%s", project_id)
    ref = upload_project_file(
        storage,
        project_id=project_id,
        category="source",
        local_path=path,
        filename=original_filename or path.name,
        content_type=mime_type or None,
    )
    ref.source_type = source_type
    ref.source_url = source_url
    ref.mime_type = mime_type or ref.mime_type
    ref.local_path = str(path.resolve())
    logger.info("STORAGE_UPLOAD_SUCCEEDED path=%s", ref.storage_path)
    return ref


def hydrate_local_media(
    ref: MediaRef | dict[str, Any] | None,
    *,
    dest_path: str | Path | None = None,
) -> str:
    """Ensure a local working copy exists; download from storage if needed."""
    media = ref if isinstance(ref, MediaRef) else MediaRef.from_dict(ref)  # type: ignore[arg-type]
    if media is None:
        raise FileNotFoundError("No media reference provided for hydration")
    if media.local_path:
        local = Path(media.local_path)
        if local.is_file() and local.stat().st_size > 0:
            return str(local.resolve())
    target = Path(dest_path) if dest_path else None
    if target is None:
        from core.paths import ensure_media_dir

        name = Path(media.storage_path).name or "source.bin"
        target = ensure_media_dir() / f"{media.project_id}_{name}"
    storage = get_object_storage()
    if not media.storage_path:
        raise FileNotFoundError("Media reference has no storage_path")
    path = storage.download_file(media.storage_path, target)
    media.local_path = str(path)
    return str(path)


def sync_project_artifacts(
    project_id: str,
    project_dir: str | Path,
    *,
    extra_files: Iterable[tuple[str, Path]] | None = None,
) -> list[MediaRef]:
    """Upload known deliverables under project_dir to durable storage."""
    root = Path(project_dir)
    storage = get_object_storage()
    uploaded: list[MediaRef] = []

    def _try_upload(category: str, file_path: Path) -> None:
        if not file_path.is_file() or file_path.stat().st_size <= 0:
            return
        ref = upload_project_file(
            storage,
            project_id=project_id,
            category=category,
            local_path=file_path,
            filename=file_path.name,
        )
        uploaded.append(ref)
        logger.info(
            "STORAGE_UPLOAD_SUCCEEDED category=%s path=%s",
            category,
            ref.storage_path,
        )

    for category, relatives in DEFAULT_ARTIFACT_GLOBS.items():
        for rel in relatives:
            _try_upload(category, root / rel)

    shorts_dir = root / "renders" / "shorts"
    if shorts_dir.is_dir():
        for short in sorted(shorts_dir.glob("short_*.mp4")):
            _try_upload("shorts", short)
    project_shorts = root / "shorts"
    if project_shorts.is_dir():
        for short in sorted(project_shorts.glob("short_*.mp4")):
            _try_upload("shorts", short)
    clips_dir = root / "clips"
    if clips_dir.is_dir():
        for short in sorted(clips_dir.glob("short_*.mp4")):
            _try_upload("shorts", short)

    audio_dir = root / "audio"
    if audio_dir.is_dir():
        for audio in list(audio_dir.glob("*.mp3")) + list(audio_dir.glob("*.wav")):
            _try_upload("audio", audio)

    if extra_files:
        for category, path in extra_files:
            _try_upload(category, Path(path))

    # Persist lightweight output manifest for UI / downloads
    try:
        import json
        from tools.media.validate_video import validate_video

        manifest_items: list[dict[str, Any]] = []
        for ref in uploaded:
            local = root
            # Prefer matching local file by name under common folders
            candidates = list(root.rglob(Path(ref.storage_path).name))
            local_path = candidates[0] if candidates else None
            duration = 0.0
            size_bytes = int(ref.file_size or 0)
            if local_path and local_path.is_file():
                size_bytes = int(local_path.stat().st_size)
                if local_path.suffix.lower() == ".mp4":
                    duration = float(validate_video(local_path).duration or 0.0)
            manifest_items.append(
                {
                    "project_id": project_id,
                    "type": "video" if ref.storage_path.endswith(".mp4") else "file",
                    "format": Path(ref.storage_path).suffix.lstrip(".") or "bin",
                    "storage_path": ref.storage_path,
                    "duration": duration,
                    "size_bytes": size_bytes,
                }
            )
        exports = root / "exports"
        exports.mkdir(parents=True, exist_ok=True)
        manifest_path = exports / "output_manifest.json"
        manifest_path.write_text(
            json.dumps({"project_id": project_id, "artifacts": manifest_items}, indent=2),
            encoding="utf-8",
        )
        _try_upload("exports", manifest_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("output_manifest write skipped: %s", type(exc).__name__)

    return uploaded


def signed_url_for(
    storage_path: str,
    *,
    bucket: str | None = None,
    expires_in: int = 3600,
) -> str:
    """Return a signed (or local file) URL for UI preview/download."""
    _ = bucket
    storage = get_object_storage()
    return storage.get_signed_url(storage_path, expires_in=expires_in)
