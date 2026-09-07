"""Lean path references for LangGraph state (path-only migration)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ProjectRefs(BaseModel):
    """Disk paths for agent artifacts — prefer these over embedded packs."""

    project_dir: str | None = None
    transcript_path: str | None = None
    analysis_path: str | None = None
    scenes_path: str | None = None
    clips_path: str | None = None
    research_path: str | None = None
    stories_path: str | None = None
    scripts_path: str | None = None
    storyboard_path: str | None = None
    captions_path: str | None = None
    platform_path: str | None = None
    seo_path: str | None = None
    trend_path: str | None = None
    thumbnail_path: str | None = None
    analytics_path: str | None = None
    shared_ai_analysis_path: str | None = None
    objects_path: str | None = None
    competitor_path: str | None = None
    render_path: str | None = None
    export_path: str | None = None
    brand_path: str | None = None
    calendar_path: str | None = None

    def merge_into_state(self) -> dict[str, Any]:
        """Return non-empty path fields suitable for WorkflowState updates."""
        data = self.model_dump(exclude_none=True)
        return {k: v for k, v in data.items() if v}


# Pack key → ProjectRefs field / relative artifact (dual-write helpers)
PACK_TO_REF: dict[str, tuple[str, str]] = {
    "transcript": ("transcript_path", "transcripts/transcript.json"),
    "speech_transcript": ("transcript_path", "transcripts/transcript.json"),
    "analysis": ("analysis_path", "analysis/understanding.json"),
    "scenes": ("scenes_path", "analysis/scenes.json"),
    "clips": ("clips_path", "clips/clips.json"),
    "research_report": ("research_path", "analysis/research_report.json"),
    "stories": ("stories_path", "analysis/stories.json"),
    "scripts": ("scripts_path", "analysis/scripts.json"),
    "storyboard_pack": ("storyboard_path", "analysis/storyboard_plan.json"),
    "captions_pack": ("captions_path", "captions/captions.srt"),
    "platform_pack": ("platform_path", "analysis/platform_plan.json"),
    "seo_pack": ("seo_path", "analysis/seo_plan.json"),
    "trend_pack": ("trend_path", "analysis/trend_plan.json"),
    "thumbnail_pack": ("thumbnail_path", "analysis/thumbnail_plan.json"),
    "analytics_pack": ("analytics_path", "analysis/analytics_plan.json"),
    "render_pack": ("render_path", "analysis/render_plan.json"),
    "export_pack": ("export_path", "exports/manifest.json"),
    "brand_pack": ("brand_path", "analysis/brand_plan.json"),
    "calendar_pack": ("calendar_path", "analysis/calendar_plan.json"),
}


def refs_from_project_dir(project_dir: str | None) -> dict[str, Any]:
    """Build default path hints for a project root (may not exist yet)."""
    if not project_dir:
        return {}
    root = project_dir.rstrip("/\\")
    refs = ProjectRefs(
        project_dir=root,
        transcript_path=f"{root}/transcripts/transcript.json",
        analysis_path=f"{root}/analysis/understanding.json",
        scenes_path=f"{root}/analysis/scenes.json",
        clips_path=f"{root}/clips/clips.json",
        research_path=f"{root}/analysis/research_report.json",
        stories_path=f"{root}/analysis/stories.json",
        scripts_path=f"{root}/analysis/scripts.json",
        storyboard_path=f"{root}/analysis/storyboard_plan.json",
        captions_path=f"{root}/captions/captions.srt",
        platform_path=f"{root}/analysis/platform_plan.json",
        seo_path=f"{root}/analysis/seo_plan.json",
        trend_path=f"{root}/analysis/trend_plan.json",
        thumbnail_path=f"{root}/analysis/thumbnail_plan.json",
        analytics_path=f"{root}/analysis/analytics_plan.json",
        shared_ai_analysis_path=f"{root}/analysis/shared_ai_analysis.json",
        objects_path=f"{root}/analysis/objects.json",
        competitor_path=f"{root}/analysis/competitor_pack.json",
        render_path=f"{root}/analysis/render_plan.json",
        export_path=f"{root}/exports/manifest.json",
        brand_path=f"{root}/analysis/brand_plan.json",
        calendar_path=f"{root}/analysis/calendar_plan.json",
    )
    return refs.merge_into_state()


def dual_write_paths(
    state_update: dict[str, Any],
    *,
    project_dir: str | None = None,
    written_paths: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Attach path refs alongside packs (Phase 1 dual-write).

    ``written_paths`` maps pack keys to absolute paths actually written.
    """
    out = dict(state_update)
    root = project_dir or out.get("project_dir")
    if root and not out.get("project_dir"):
        out["project_dir"] = root
    if root:
        for key, val in refs_from_project_dir(str(root)).items():
            out.setdefault(key, val)
    if written_paths:
        for pack_key, path in written_paths.items():
            meta = PACK_TO_REF.get(pack_key)
            if meta:
                out[meta[0]] = path
            elif pack_key.endswith("_path"):
                out[pack_key] = path
    return out
