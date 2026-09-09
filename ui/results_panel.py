"""Results panel — Creator OS stage-grouped deliverables."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _show_json_or_info(value: Any, empty: str) -> None:
    if isinstance(value, dict) and value:
        st.json(value)
    elif value:
        st.write(value)
    else:
        st.info(empty)


def render_results_panel(result: dict[str, Any] | None = None) -> None:
    """Secondary Creator OS tabs — primary players/downloads live in output_panel."""
    data = result or st.session_state.get("last_result")
    if not isinstance(data, dict) or not data:
        return

    st.subheader("Creator OS — agent packages")
    st.caption(
        "Detailed stage outputs. Use **Video Results** above for playable MP4s, "
        "Shorts, before/after, and ZIP downloads (validated files only)."
    )
    project_dir = data.get("project_dir") or ""
    if project_dir:
        st.caption(f"Project folder: `{project_dir}`")

    output_files = _as_dict(data.get("output_files"))
    folders = _as_dict(output_files.get("folders"))

    tabs = st.tabs(
        [
            "Research",
            "Planning",
            "Script",
            "Storyboard",
            "Video",
            "Optimization",
            "Analytics",
            "Publishing",
            "Files",
        ]
    )

    with tabs[0]:
        st.markdown("**Research**")
        clips = _as_dict(data.get("selected_clips") or data.get("clips"))
        items = clips.get("clips") if isinstance(clips.get("clips"), list) else []
        if not items and isinstance(clips.get("report"), dict):
            items = clips["report"].get("clips") or []
        if items:
            for i, clip in enumerate(items[:20]):
                if not isinstance(clip, dict):
                    continue
                st.markdown(
                    f"**Clip {clip.get('id', i)}** · "
                    f"{clip.get('start', '?')}s → {clip.get('end', '?')}s · "
                    f"target={clip.get('target_duration', '')}s · "
                    f"score={clip.get('score', clip.get('final_score', ''))}"
                )
        research = data.get("research_report") or data.get("research")
        if research:
            with st.expander("Research report", expanded=not items):
                st.json(research)
        podcast = data.get("podcast_clips")
        if podcast:
            with st.expander("Podcast clips"):
                st.json(podcast)
        if not items and not research and not podcast:
            st.info("No research / clip packages for this job.")

    with tabs[1]:
        st.markdown("**Planning**")
        for key, label in (
            ("stories", "Stories"),
            ("video_type_pack", "Video type"),
            ("visual_style_pack", "Visual style"),
            ("brand_pack", "Brand kit"),
            ("calendar_pack", "Content calendar"),
            ("content_calendar", "Content calendar"),
        ):
            val = data.get(key)
            if val:
                with st.expander(label):
                    st.json(val)
        if not any(
            data.get(k)
            for k in (
                "stories",
                "video_type_pack",
                "visual_style_pack",
                "brand_pack",
                "calendar_pack",
                "content_calendar",
            )
        ):
            st.info("No planning packs available.")

    with tabs[2]:
        st.markdown("**Script & localization**")
        scripts = data.get("scripts")
        if scripts:
            st.json(scripts)
        locs = data.get("localizations") or data.get("cultural_context")
        if isinstance(locs, dict):
            with st.expander("Localization"):
                st.json(locs)
        humor = data.get("humor_context") or data.get("humor_localization")
        if humor:
            with st.expander("Humor context"):
                st.json(humor)
        if not scripts and not locs:
            st.info("No scripts / localization for this job.")

    with tabs[3]:
        st.markdown("**Storyboard**")
        for key, label in (
            ("storyboard_pack", "Storyboard"),
            ("storyboard", "Storyboard"),
            ("image_pack", "Images"),
            ("motion_graphics_pack", "Motion graphics"),
        ):
            val = data.get(key)
            if val:
                with st.expander(label):
                    st.json(val)
        if not any(
            data.get(k)
            for k in (
                "storyboard_pack",
                "storyboard",
                "image_pack",
                "motion_graphics_pack",
            )
        ):
            st.info("No storyboard / image packs (enable Storyboard / Image Generation).")

    with tabs[4]:
        st.markdown("**Video Creation**")
        video_path = str(data.get("video_path") or "").strip()
        finals = folders.get("final") or []
        if not video_path and finals:
            video_path = str(finals[0])
        if video_path and Path(video_path).is_file():
            from tools.media.validate_video import validate_video

            v = validate_video(video_path)
            if v.ok:
                st.video(video_path)
                st.caption(
                    f"{video_path} · {v.duration:.1f}s · {v.width}x{v.height}"
                )
                if Path(video_path).stat().st_size > 0:
                    try:
                        st.download_button(
                            label="Download Full Video",
                            data=Path(video_path).read_bytes(),
                            file_name=Path(video_path).name,
                            mime="video/mp4",
                            key="results_dl_full",
                        )
                    except Exception:  # noqa: BLE001
                        pass
            else:
                st.warning(
                    f"Full video present but not validated: {v.reason}. "
                    "See Video Results for status."
                )
        else:
            st.info(
                "No rendered video file for this run "
                "(script-only / soft-skip is expected without media)."
            )
        tip = data.get("transform_intent") or {}
        if isinstance(tip, dict) and tip:
            plan = tip.get("plan") if isinstance(tip.get("plan"), dict) else tip
            intent = plan.get("intent") if isinstance(plan.get("intent"), dict) else {}
            if intent and not plan.get("skipped"):
                st.markdown(
                    f"**Transform:** Changed {intent.get('scenes_changed', 1)} of "
                    f"{intent.get('scenes_total', '?')} scenes · "
                    f"preserved {intent.get('scenes_preserved', '?')}"
                )
        shorts = folders.get("shorts") or []
        if shorts:
            st.markdown("**Multi Shorts exports**")
            for i, sp in enumerate(shorts):
                sp_s = str(sp)
                st.caption(sp_s)
                if Path(sp_s).is_file():
                    st.video(sp_s)
                    try:
                        st.download_button(
                            label=f"Download {Path(sp_s).name}",
                            data=Path(sp_s).read_bytes(),
                            file_name=Path(sp_s).name,
                            mime="video/mp4",
                            key=f"results_dl_short_{i}",
                        )
                    except Exception:  # noqa: BLE001
                        pass
        captions = _as_dict(data.get("captions") or data.get("captions_pack"))
        for key, label in (
            ("srt_path", "SRT"),
            ("vtt_path", "VTT"),
            ("ass_path", "ASS"),
        ):
            path = str(captions.get(key) or "").strip()
            if path:
                st.markdown(f"**{label}:** `{path}`")
        report = data.get("quality_report") or _as_dict(data.get("quality_pack")).get(
            "report"
        )
        report = _as_dict(report)
        if report:
            st.markdown(
                f"**Quality passed:** `{report.get('passed')}` · "
                f"**skipped:** `{report.get('skipped')}`"
            )

    with tabs[5]:
        st.markdown("**Optimization**")
        for key, label in (
            ("platform_pack", "Platform"),
            ("platform", "Platform"),
            ("seo_pack", "SEO"),
            ("seo", "SEO"),
            ("trend_pack", "Trend"),
            ("trend", "Trend"),
            ("repurpose_pack", "Repurpose"),
            ("repurpose", "Repurpose"),
            ("thumbnail_pack", "Thumbnail"),
            ("thumbnail", "Thumbnail"),
        ):
            val = data.get(key)
            if val:
                with st.expander(label):
                    st.json(val)
        meta = data.get("platform_metadata")
        if meta:
            with st.expander("Platform metadata"):
                st.json(meta)
        thumbs = folders.get("thumbnails") or []
        for t in thumbs[:3]:
            if Path(str(t)).is_file():
                st.image(str(t), caption=str(t), use_container_width=True)

    with tabs[6]:
        st.markdown("**Analytics prediction**")
        analytics = data.get("analytics_pack") or data.get("analytics")
        _show_json_or_info(
            analytics,
            "No analytics prediction (enable Analytics Prediction feature).",
        )

    with tabs[7]:
        st.markdown("**Publishing Preparation**")
        st.caption(
            "Plan-only export package — no live social publish / OAuth in this MVP."
        )
        export_pack = _as_dict(data.get("export_pack"))
        _show_json_or_info(export_pack, "No export pack yet.")
        if project_dir:
            p = Path(project_dir) / "exports" / "platform_metadata.json"
            if p.is_file():
                st.caption(f"Platform metadata on disk: `{p}`")
            m = Path(project_dir) / "exports" / "manifest.json"
            if m.is_file():
                st.caption(f"Manifest: `{m}`")

    with tabs[8]:
        st.markdown("**Files**")
        if project_dir:
            root = Path(project_dir)
            interesting = [
                "analysis/research_report.json",
                "analysis/scripts.json",
                "analysis/storyboard_plan.json",
                "analysis/brand_plan.json",
                "analysis/calendar_plan.json",
                "analysis/seo_plan.json",
                "analysis/thumbnail_plan.json",
                "analysis/analytics_plan.json",
                "analysis/platform_plan.json",
                "analysis/quality_report.json",
                "exports/manifest.json",
                "exports/platform_metadata.json",
            ]
            for rel in interesting:
                p = root / rel
                st.write(("✅" if p.is_file() else "⚪") + f" `{rel}`")
            aliases = _as_dict(output_files.get("aliases"))
            if aliases:
                with st.expander("output_files.aliases"):
                    st.json(aliases)
        elif not project_dir:
            st.info("No project directory on this result.")
