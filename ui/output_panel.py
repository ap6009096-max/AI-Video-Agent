"""Final Output Panel — video player, download buttons, scene editor, and versioning.

Renders when a job finishes successfully.  Provides:
1. 🎬 playable MP4 video player (st.video)
2. Download buttons (Video, Audio, Captions SRT/VTT)
3. Scene timeline preview & natural-language per-scene editor
4. Version rollback controls (v1 / v2 / v3 / current)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from core.versioning import get_final_video_path, list_versions, rollback


def render_final_output_panel(result: dict[str, Any] | None = None) -> None:
    """Render final video deliverable, download buttons, scene timeline, and scene editor."""
    data = result or st.session_state.get("last_result")
    if not isinstance(data, dict) or not data:
        return

    project_dir = data.get("project_dir") or st.session_state.get("resume_project_id", "")
    if not project_dir:
        return

    root = Path(project_dir)
    final_video = get_final_video_path(root)

    st.divider()
    st.subheader("🎬 YOUR VIDEO IS READY")

    # Layout: Video player on left, Details & Download on right
    v_col, d_col = st.columns([3, 2])

    with v_col:
        if final_video and final_video.is_file():
            st.video(str(final_video))
            st.caption(f"Video file: `{final_video.name}` ({final_video.stat().st_size / 1024 / 1024:.1f} MB)")
        else:
            st.info("No encoded MP4 file generated. (Check logs or FFmpeg PATH if unexpected).")

    with d_col:
        # Deliverable Metadata
        mode = data.get("output_mode") or "Video Transformation"
        st.markdown(f"**Mode:** `{mode}`")
        if final_video and final_video.is_file():
            st.markdown("**Status:** ✅ `Rendered & Encoded`")
        else:
            st.markdown("**Status:** ℹ️ `Analysis & Plan Only`")

        st.markdown("---")
        st.markdown("**Downloads & Deliverables**")

        # Download Video Button
        if final_video and final_video.is_file():
            try:
                st.download_button(
                    label="⬇️ Download Video (MP4)",
                    data=final_video.read_bytes(),
                    file_name=final_video.name,
                    mime="video/mp4",
                    use_container_width=True,
                )
            except Exception:  # noqa: BLE001
                st.caption(f"File ready at: `{final_video}`")

        # Download Audio Button
        audio_path = root / "audio" / "final_voice.wav"
        if not audio_path.is_file():
            # Check for any audio file
            audio_files = list((root / "audio").glob("*.mp3")) + list((root / "audio").glob("*.wav"))
            if audio_files:
                audio_path = audio_files[0]

        if audio_path.is_file():
            st.download_button(
                label="🎵 Download Audio",
                data=audio_path.read_bytes(),
                file_name=audio_path.name,
                mime="audio/wav" if audio_path.suffix == ".wav" else "audio/mpeg",
                use_container_width=True,
            )

        # Download Subtitles Button
        sub_path = root / "captions" / "subtitles.srt"
        if not sub_path.is_file():
            sub_files = list((root / "captions").glob("*.srt")) + list((root / "captions").glob("*.vtt"))
            if sub_files:
                sub_path = sub_files[0]

        if sub_path.is_file():
            st.download_button(
                label="📝 Download Captions (SRT)",
                data=sub_path.read_text(encoding="utf-8"),
                file_name=sub_path.name,
                mime="text/plain",
                use_container_width=True,
            )

    # -----------------------------------------------------------------------
    # Scene Timeline & Per-Scene Editor
    # -----------------------------------------------------------------------
    st.divider()
    st.markdown("### 🎞️ Scene Timeline & Editor")

    scenes_data = data.get("animation_plan") or data.get("scenes") or {}
    scene_list = []
    if isinstance(scenes_data, dict):
        scene_list = scenes_data.get("scenes") or []

    if scene_list:
        for idx, scene in enumerate(scene_list):
            if not isinstance(scene, dict):
                continue
            sc_id = scene.get("scene_id", f"scene_{idx+1:03d}")
            speaker = scene.get("speaker", f"Speaker {idx+1}")
            dialogue = scene.get("dialogue", "")
            duration = scene.get("duration", 0.0)
            camera = scene.get("camera", "medium shot")

            with st.expander(f"Scene {idx+1} ({sc_id}) — {speaker} [{duration}s] · {camera}", expanded=False):
                st.markdown(f"**Dialogue:** *\"{dialogue}\"*")
                if scene.get("visual_cue"):
                    st.markdown(f"**Visual:** `{scene.get('visual_cue')}`")

                # Per-Scene Edit Controls
                e_col1, e_col2 = st.columns([3, 1])
                with e_col1:
                    edit_prompt = st.text_input(
                        "Edit instruction for this scene",
                        placeholder="e.g., 'Make this scene funnier', 'Change dialogue to...', 'Use uploaded voice'",
                        key=f"edit_prompt_{sc_id}",
                    )
                with e_col2:
                    if st.button("REGENERATE SCENE", key=f"re_edit_btn_{sc_id}"):
                        if edit_prompt.strip():
                            st.info(f"Submitting scene edit for `{sc_id}`: *{edit_prompt}*")
                            # Stash edit request into session and prompt user to rerun job
                            st.session_state["scene_edit_request"] = {
                                "scene_id": sc_id,
                                "instruction": edit_prompt.strip(),
                            }
                            st.rerun()
                        else:
                            st.warning("Please enter an edit instruction.")
    else:
        st.info("No scene timeline available for this run.")

    # -----------------------------------------------------------------------
    # Versioning & Rollback Controls
    # -----------------------------------------------------------------------
    versions = list_versions(root)
    if versions:
        st.divider()
        st.markdown("### 🔄 Version History & Rollback")
        v_labels = [f"v{v.get('version')}" for v in versions]
        selected_v = st.selectbox("Select Version to Restore", options=v_labels)
        if st.button("RESTORE VERSION"):
            v_num = int(selected_v.replace("v", ""))
            if rollback(root, v_num):
                st.success(f"Restored `{selected_v}` to current output!")
                st.rerun()
            else:
                st.error(f"Failed to restore `{selected_v}`.")

