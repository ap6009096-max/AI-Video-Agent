"""Results dashboard — real playable media, downloads, before/after, ZIP."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any

import streamlit as st

from core.versioning import get_final_video_path, list_versions, rollback
from tools.media.validate_video import validate_video


def _load_transform_intent(root: Path) -> dict[str, Any]:
    path = root / "analysis" / "transform_intent.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _load_quality_passed(root: Path, result: dict[str, Any]) -> bool | None:
    report = result.get("quality_report") or {}
    if isinstance(report, dict) and "passed" in report:
        return bool(report.get("passed"))
    if isinstance(report, dict) and isinstance(report.get("report"), dict):
        return bool(report["report"].get("passed"))
    qpath = root / "analysis" / "quality_report.json"
    if qpath.is_file():
        try:
            data = json.loads(qpath.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                rep = data.get("report") if isinstance(data.get("report"), dict) else data
                if isinstance(rep, dict) and "passed" in rep:
                    return bool(rep.get("passed"))
        except Exception:  # noqa: BLE001
            pass
    return None


def _short_paths(root: Path, result: dict[str, Any]) -> list[Path]:
    found: list[Path] = []
    folders = (result.get("output_files") or {}).get("folders") if isinstance(
        result.get("output_files"), dict
    ) else {}
    shorts = folders.get("shorts") if isinstance(folders, dict) else None
    if isinstance(shorts, list):
        for sp in shorts:
            p = Path(str(sp))
            if p.is_file() and p not in found:
                found.append(p)
    for folder in (root / "renders" / "shorts", root / "shorts"):
        if folder.is_dir():
            for p in sorted(folder.glob("short_*.mp4")):
                if p.is_file() and p not in found:
                    found.append(p)
    return found


def _resolve_root(project_dir: str) -> Path | None:
    root = Path(project_dir)
    if root.is_dir():
        return root
    from core.paths import get_project_dir

    try:
        candidate = get_project_dir(str(project_dir))
        return candidate if candidate.is_dir() else None
    except Exception:  # noqa: BLE001
        return None


def _signed_play_url(data: dict[str, Any], storage_path: str) -> str | None:
    try:
        from storage.sync import signed_url_for

        url = signed_url_for(storage_path, expires_in=3600)
        if url and not str(url).startswith("file:"):
            return str(url)
    except Exception:  # noqa: BLE001
        return None
    return None


def _download_bytes(path: Path) -> bytes | None:
    try:
        if path.is_file() and path.stat().st_size > 0:
            return path.read_bytes()
    except Exception:  # noqa: BLE001
        return None
    return None


def _build_zip(files: list[tuple[str, Path]]) -> bytes | None:
    buf = io.BytesIO()
    count = 0
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for arcname, path in files:
            if path.is_file() and path.stat().st_size > 0:
                zf.write(path, arcname=arcname)
                count += 1
    if count == 0:
        return None
    return buf.getvalue()


def _status_line(ok: bool, label: str) -> None:
    if ok:
        st.markdown(f"✓ **{label} Ready**")
    else:
        st.markdown(f"⚠ **{label} Not Available**")


def render_final_output_panel(result: dict[str, Any] | None = None) -> None:
    """Unified Results dashboard: Full → Shorts → Before/After → Downloads."""
    data = result or st.session_state.get("last_result")
    if not isinstance(data, dict) or not data:
        return

    project_dir = data.get("project_dir") or st.session_state.get("resume_project_id", "")
    if not project_dir:
        return
    root = _resolve_root(str(project_dir))
    if root is None:
        return

    final_video = get_final_video_path(root)
    full_validation = validate_video(final_video) if final_video else None
    quality_passed = _load_quality_passed(root, data)
    video_ready = bool(
        full_validation
        and full_validation.ok
        and quality_passed is not False
    )

    shorts_raw = _short_paths(root, data)
    shorts_valid: list[tuple[Path, Any]] = []
    for sp in shorts_raw:
        v = validate_video(sp)
        if v.ok:
            shorts_valid.append((sp, v))

    tip = _load_transform_intent(root)
    plan = tip.get("plan") if isinstance(tip.get("plan"), dict) else {}
    intent = plan.get("intent") if isinstance(plan.get("intent"), dict) else {}

    st.divider()
    st.subheader("Video Results" if video_ready else "Output")

    # Deliverable status strip
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _status_line(video_ready, "Full Video")
    with c2:
        _status_line(bool(shorts_valid), "Short Video")
    with c3:
        caps_ok = any(
            (root / "captions" / n).is_file() or (root / "subtitles" / n).is_file()
            for n in ("captions.srt", "captions.vtt", "captions.ass")
        )
        _status_line(caps_ok, "Captions")
    with c4:
        thumb = root / "renders" / "thumbnail.jpg"
        if not thumb.is_file():
            thumb = root / "thumbnails" / "thumbnail.jpg"
        _status_line(thumb.is_file() and thumb.stat().st_size > 0, "Thumbnail")

    # Short failure message (partial success)
    short_errors = []
    render_pack = data.get("render_pack") or {}
    if isinstance(render_pack, dict):
        rplan = render_pack.get("plan") if isinstance(render_pack.get("plan"), dict) else {}
        short_errors = list(rplan.get("short_errors") or [])
    if not shorts_valid and (short_errors or data.get("multi_shorts_export")):
        st.warning(
            "Short Video Not Available\n\n"
            "The Short could not be generated.\n"
            + ("\n".join(f"- {e}" for e in short_errors) if short_errors else "")
        )

    # --- Full Video ---
    st.markdown("### Full Video")
    if video_ready and final_video is not None and full_validation is not None:
        pid = str(data.get("project_id") or data.get("job_id") or root.name)
        play_url = _signed_play_url(data, f"projects/{pid}/final/final.mp4")
        if play_url:
            st.video(play_url)
        else:
            st.video(str(final_video))
        st.caption(
            f"Duration: {full_validation.duration:.1f}s · "
            f"{full_validation.width}×{full_validation.height} · "
            f"{final_video.stat().st_size / 1024 / 1024:.1f} MB"
        )
        blob = _download_bytes(final_video)
        if blob:
            st.download_button(
                "Download Full Video",
                data=blob,
                file_name="final.mp4",
                mime="video/mp4",
                use_container_width=True,
                key="dl_full_video",
            )
    elif final_video and final_video.is_file() and quality_passed is False:
        st.error(
            "Full video generation failed.\nStage: Quality\n"
            "Reason: quality check failed — downloads disabled."
        )
    elif full_validation and not full_validation.ok:
        st.error(
            f"Full video generation failed.\nStage: Render\n"
            f"Reason: {full_validation.reason}"
        )
    else:
        st.info("No validated full MP4 yet.")

    # --- Shorts ---
    st.markdown("### Short Videos")
    if shorts_valid:
        for i, (sp, sv) in enumerate(shorts_valid):
            st.markdown(f"**{sp.name}** — Duration: {sv.duration:.1f}s")
            st.video(str(sp))
            blob = _download_bytes(sp)
            if blob:
                st.download_button(
                    f"Download Short ({sp.name})",
                    data=blob,
                    file_name=sp.name,
                    mime="video/mp4",
                    use_container_width=True,
                    key=f"dl_short_{i}",
                )
    else:
        st.caption("No validated Short MP4s for this run.")

    # --- Before / After ---
    if intent and not plan.get("skipped"):
        st.markdown("### Before / After")
        total = int(intent.get("scenes_total") or 0)
        changed = int(intent.get("scenes_changed") or 1)
        preserved = int(intent.get("scenes_preserved") or max(0, total - changed))
        st.markdown(f"**Changed:** {changed} scene(s) · **Preserved:** {preserved} scenes")
        left, right = st.columns(2)
        source_media = None
        for cand in (
            root / "source" / "youtube_video.mp4",
            Path(str((data.get("project") or {}).get("source_path") or "")),
        ):
            if cand.is_file():
                source_media = cand
                break
        if not source_media:
            srcs = list((root / "source").glob("*.mp4")) if (root / "source").is_dir() else []
            if srcs:
                source_media = srcs[0]
        with left:
            st.markdown("#### Original")
            if source_media and source_media.is_file():
                st.video(str(source_media))
            else:
                st.caption("Source scene media not available.")
        with right:
            st.markdown("#### Transformed")
            if video_ready and final_video is not None:
                st.video(str(final_video))
            else:
                st.caption("Transformed output not available.")
        with st.expander("What changed", expanded=False):
            st.markdown("**Changed**")
            for item in intent.get("regeneration_scope") or intent.get("requested_changes") or []:
                st.markdown(f"- {item}")
            st.markdown("**Preserved**")
            for item in intent.get("preserved_elements") or []:
                st.markdown(f"- {item}")

    # --- Files ---
    st.markdown("### Files")
    zip_entries: list[tuple[str, Path]] = []
    if video_ready and final_video is not None:
        zip_entries.append(("final.mp4", final_video))
    for sp, _ in shorts_valid:
        zip_entries.append((sp.name, sp))

    for label, name, mime in (
        ("SRT", "captions.srt", "text/plain"),
        ("VTT", "captions.vtt", "text/plain"),
        ("ASS", "captions.ass", "text/plain"),
    ):
        sub_path = root / "captions" / name
        if not sub_path.is_file():
            sub_path = root / "subtitles" / name
        if sub_path.is_file() and sub_path.stat().st_size > 0:
            zip_entries.append((name, sub_path))
            try:
                st.download_button(
                    f"Download Captions ({label})",
                    data=sub_path.read_text(encoding="utf-8"),
                    file_name=name,
                    mime=mime,
                    use_container_width=True,
                    key=f"dl_cap_{label}",
                )
            except Exception:  # noqa: BLE001
                pass

    audio_path = root / "audio" / "final_voice.wav"
    if not audio_path.is_file():
        audio_files = list((root / "audio").glob("*.mp3")) + list(
            (root / "audio").glob("*.wav")
        )
        audio_path = audio_files[0] if audio_files else audio_path
    if audio_path.is_file() and audio_path.stat().st_size > 0:
        zip_entries.append((audio_path.name, audio_path))
        blob = _download_bytes(audio_path)
        if blob:
            st.download_button(
                "Download Audio",
                data=blob,
                file_name=audio_path.name,
                mime="audio/mpeg" if audio_path.suffix == ".mp3" else "audio/wav",
                use_container_width=True,
                key="dl_audio",
            )

    thumb_path = root / "renders" / "thumbnail.jpg"
    if not thumb_path.is_file():
        thumb_path = root / "thumbnails" / "thumbnail.jpg"
    if thumb_path.is_file() and thumb_path.stat().st_size > 0:
        zip_entries.append((thumb_path.name, thumb_path))
        st.image(str(thumb_path), caption="Thumbnail", width=240)
        blob = _download_bytes(thumb_path)
        if blob:
            st.download_button(
                "Download Thumbnail",
                data=blob,
                file_name=thumb_path.name,
                mime="image/jpeg",
                use_container_width=True,
                key="dl_thumb",
            )

    meta_path = root / "exports" / "output_manifest.json"
    if not meta_path.is_file():
        meta_path = root / "exports" / "manifest.json"
    if meta_path.is_file() and meta_path.stat().st_size > 0:
        zip_entries.append((meta_path.name, meta_path))
        st.download_button(
            "Download Metadata (JSON)",
            data=meta_path.read_text(encoding="utf-8"),
            file_name=meta_path.name,
            mime="application/json",
            use_container_width=True,
            key="dl_meta",
        )

    zip_bytes = _build_zip(zip_entries)
    if zip_bytes:
        st.download_button(
            "Download All",
            data=zip_bytes,
            file_name="deliverables.zip",
            mime="application/zip",
            use_container_width=True,
            key="dl_all_zip",
        )

    # Scene Timeline & Per-Scene Editor
    st.divider()
    st.markdown("### Scene Timeline & Editor")
    scenes_data = data.get("animation_plan") or data.get("scenes") or {}
    scene_list = scenes_data.get("scenes") or [] if isinstance(scenes_data, dict) else []
    if scene_list:
        for idx, scene in enumerate(scene_list):
            if not isinstance(scene, dict):
                continue
            sc_id = scene.get("scene_id", f"scene_{idx+1:03d}")
            speaker = scene.get("speaker", f"Speaker {idx+1}")
            dialogue = scene.get("dialogue", "")
            duration = scene.get("duration", 0.0)
            camera = scene.get("camera", "medium shot")
            with st.expander(
                f"Scene {idx+1} ({sc_id}) — {speaker} [{duration}s] · {camera}",
                expanded=False,
            ):
                st.markdown(f'**Dialogue:** *"{dialogue}"*')
                e_col1, e_col2 = st.columns([3, 1])
                with e_col1:
                    edit_prompt = st.text_input(
                        "Edit instruction for this scene",
                        placeholder=(
                            "e.g., Make the guest's answer shorter and funnier. "
                            "Keep host, background, and music."
                        ),
                        key=f"edit_prompt_{sc_id}",
                    )
                with e_col2:
                    if st.button("REGENERATE SCENE", key=f"re_edit_btn_{sc_id}"):
                        if edit_prompt.strip():
                            st.session_state["scene_edit_request"] = {
                                "scene_id": sc_id,
                                "instruction": edit_prompt.strip(),
                                "speaker": str(speaker or ""),
                            }
                            pid = str(
                                data.get("project_id")
                                or data.get("job_id")
                                or st.session_state.get("resume_project_id")
                                or ""
                            ).strip()
                            if not pid and root.name not in {".", ".."}:
                                pid = root.name
                            if pid:
                                st.session_state["resume_project_id"] = pid
                            st.success(
                                f"Queued scene edit for `{sc_id}` on project `{pid or '?'}`. "
                                "Click **CREATE VIDEO** again to apply."
                            )
                            st.rerun()
                        else:
                            st.warning("Please enter an edit instruction.")
    else:
        st.info("No scene timeline available for this run.")

    with st.expander("Job / agent details", expanded=False):
        st.json(
            {
                "project_dir": str(root),
                "mode": data.get("output_mode"),
                "quality_passed": quality_passed,
                "full_validation": full_validation.to_dict() if full_validation else None,
                "short_count": len(shorts_valid),
                "short_errors": short_errors,
            }
        )

    versions = list_versions(root)
    if versions:
        st.divider()
        st.markdown("### Version History & Rollback")
        v_labels = [f"v{v.get('version')}" for v in versions]
        selected_v = st.selectbox("Select Version to Restore", options=v_labels)
        if st.button("RESTORE VERSION"):
            v_num = int(selected_v.replace("v", ""))
            if rollback(root, v_num):
                st.success(f"Restored `{selected_v}` to current output!")
                st.rerun()
            else:
                st.error(f"Failed to restore `{selected_v}`.")
