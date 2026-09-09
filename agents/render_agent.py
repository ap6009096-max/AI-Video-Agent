"""Render Agent — compose final MP4 + thumbnail (no Gemini)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from agents.base import BaseAgent
from core.errors import RenderAgentError, StorageError
from core.logging import get_logger
from core.paths import (
    ensure_project_analysis_dir,
    ensure_project_dir,
    ensure_project_renders_dir,
    get_render_plan_path,
)
from schemas.job import FeatureFlags, VideoJobConfig
from schemas.project import ProjectMetadata
from schemas.render import RenderOp, RenderPack, RenderPlan, RenderResult
from tools.ffmpeg.audio_ops import normalize_loudness, sync_voice_to_video
from tools.ffmpeg.bin import resolve_ffmpeg_binary
from tools.ffmpeg.edit import concat_segments, cut_segment
from tools.ffmpeg.encode import encode_mp4
from tools.ffmpeg.subs import burn_subtitles
from tools.ffmpeg.thumb import extract_thumbnail
from tools.ffmpeg.transform import resize
from tools.media.validate_video import validate_video

logger = get_logger(__name__)


def _aspect_dims(aspect: str, default_w: int = 1080, default_h: int = 1920) -> tuple[int, int]:
    mapping = {
        "9:16": (1080, 1920),
        "16:9": (1920, 1080),
        "1:1": (1080, 1080),
        "4:5": (1080, 1350),
        "3:4": (1080, 1440),
    }
    key = (aspect or "").strip()
    if key in mapping:
        return mapping[key]
    try:
        a, b = key.split(":", 1)
        ratio = float(a) / float(b)
        if ratio < 1:
            return default_w, int(round(default_w / ratio))
        return int(round(default_h * ratio)), default_h
    except (ValueError, ZeroDivisionError):
        return default_w, default_h


class RenderAgent(BaseAgent):
    """Write render_plan.json first; compose renders/final.mp4 when possible."""

    name = "render"

    def run(
        self,
        project: ProjectMetadata | dict[str, Any],
        *,
        project_dir: str | Path | None = None,
        config: VideoJobConfig | dict[str, Any] | None = None,
        features: FeatureFlags | dict[str, Any] | None = None,
        clips: dict[str, Any] | None = None,
        captions_pack: dict[str, Any] | None = None,
        reframe_pack: dict[str, Any] | None = None,
        voice_pack: dict[str, Any] | None = None,
        music_pack: dict[str, Any] | None = None,
        avatar_pack: dict[str, Any] | None = None,
        platform_pack: dict[str, Any] | None = None,
        source_metadata: dict[str, Any] | None = None,
        speech_transcript: dict[str, Any] | None = None,
        transform_intent_pack: dict[str, Any] | None = None,
        scenes: dict[str, Any] | None = None,
        **_: Any,
    ) -> RenderResult:
        _ = music_pack  # music bed reserved
        meta = self._coerce_project(project)
        project_id = meta.project_id
        root = Path(project_dir) if project_dir else ensure_project_dir(project_id)
        root.mkdir(parents=True, exist_ok=True)
        job_config = self._coerce_config(config)

        tw, th, aspect = self._resolve_target(reframe_pack, platform_pack, job_config)
        source = self._resolve_source(
            root, meta, reframe_pack, captions_pack, source_metadata, speech_transcript
        )
        burn, caption_path = self._caption_burn_info(captions_pack, platform_pack)

        ops: list[RenderOp] = []
        notes_parts: list[str] = []
        if isinstance(avatar_pack, dict):
            aplan = avatar_pack.get("plan") or {}
            if isinstance(aplan, dict) and not aplan.get("skipped") and aplan.get("avatar_type"):
                notes_parts.append(
                    f"Avatar planned ({aplan.get('avatar_type')}) — "
                    "composite deferred (MVP plan-only)."
                )
        renders = root / "renders"
        renders.mkdir(parents=True, exist_ok=True)
        try:
            ensure_project_renders_dir(project_id)
        except Exception:  # noqa: BLE001
            pass

        out_video = renders / "final.mp4"
        out_thumb = renders / "thumbnail.jpg"

        plan = RenderPlan(
            project_id=project_id,
            source_path=str(source) if source else "",
            ops=ops,
            target_width=tw,
            target_height=th,
            target_aspect=aspect,
            burn_captions=burn,
            caption_path=caption_path,
            output_path=str(out_video),
            thumbnail_path=str(out_thumb),
            encoded=False,
            skipped=source is None,
            notes="Render plan created.",
        )
        pack = RenderPack(plan=plan, notes=plan.notes)
        path = self._write_pack(project_id, root, pack)
        messages = [
            f"[{self.name}] Plan written target={aspect} {tw}x{th}",
            f"[{self.name}] Wrote analysis/render_plan.json",
        ]

        if source is None:
            plan.skipped = True
            plan.notes = "No media — plan only (soft-skip encode)."
            pack.notes = plan.notes
            path = self._write_pack(project_id, root, pack)
            messages.append(f"[{self.name}] Encode soft-skipped (no media).")
            return RenderResult(
                render_pack=pack, render_path=str(path), messages=messages
            )

        if resolve_ffmpeg_binary() is None:
            plan.skipped = True
            plan.notes = "FFmpeg unavailable — plan only (soft-skip encode)."
            pack.notes = plan.notes
            path = self._write_pack(project_id, root, pack)
            messages.append(f"[{self.name}] Encode soft-skipped (no FFmpeg).")
            return RenderResult(
                render_pack=pack, render_path=str(path), messages=messages
            )

        work = source
        transform_failed = False
        try:
            # Selective scene transform (Phase 1) — stitch changed window + preserve rest
            sel_work, sel_ops, sel_metrics = self._apply_selective_transform(
                work,
                transform_intent_pack,
                scenes,
                renders,
                voice_pack=voice_pack,
                project_dir=root,
            )
            if sel_ops:
                ops.extend(sel_ops)
            if sel_work is not None and sel_work.is_file():
                work = sel_work
                messages.append(
                    f"[{self.name}] Selective transform applied "
                    f"(changed={sel_metrics.get('scenes_changed')} "
                    f"preserved={sel_metrics.get('scenes_preserved')})"
                )
                # Ensure at least one Short from the changed window when multi-shorts on
                short_extra = self._export_transform_short(
                    work if sel_metrics.get("applied") else source,
                    renders,
                    features=features,
                    start=float(sel_metrics.get("start") or 0.0),
                    end=float(sel_metrics.get("end") or 0.0),
                    source_media=source,
                )
                if short_extra:
                    plan.short_paths = list(plan.short_paths) + [str(p) for p in short_extra]
                    for p in short_extra:
                        ops.append(RenderOp(name="export_short", detail=str(p)))

            work, clip_ops, short_paths, short_errors = self._apply_clips(
                work,
                clips,
                renders,
                features=features,
                target_width=tw,
                target_height=th,
            )
            ops.extend(clip_ops)
            if short_errors:
                plan.short_errors = list(short_errors)
                for err in short_errors:
                    messages.append(
                        f"[{self.name}] Short creation failed. "
                        f"Stage: Short Render. Reason: {err}"
                    )
            if short_paths:
                existing = list(plan.short_paths or [])
                for p in short_paths:
                    sp = str(p)
                    if sp not in existing:
                        existing.append(sp)
                plan.short_paths = existing
                messages.append(
                    f"[{self.name}] Shorts exported: {len(short_paths)} "
                    f"under renders/shorts/"
                )

            if burn and caption_path and Path(caption_path).is_file():
                burned = renders / "_burned.mp4"
                result = burn_subtitles(work, caption_path, burned)
                if result is not None:
                    work = result
                    ops.append(RenderOp(name="burn_subtitles", detail=caption_path))
                else:
                    notes_parts.append("Caption burn soft-failed.")

            if tw > 0 and th > 0:
                resized = renders / "_resized.mp4"
                result = resize(work, resized, width=tw, height=th)
                if result is not None:
                    work = result
                    ops.append(RenderOp(name="resize", detail=f"{tw}x{th}"))
                else:
                    # Fallback encode with pad/scale
                    result = encode_mp4(work, resized, width=tw, height=th)
                    if result is not None:
                        work = result
                        ops.append(RenderOp(name="encode_resize", detail=f"{tw}x{th}"))
                    else:
                        transform_failed = True

            normalized = renders / "_loudnorm.mp4"
            result = normalize_loudness(work, normalized)
            if result is not None:
                work = result
                ops.append(RenderOp(name="normalize_loudness", detail="loudnorm"))
            else:
                notes_parts.append("Loudnorm soft-skipped.")

            # Final copy/encode to final.mp4
            if not transform_failed and work.resolve() != out_video.resolve():
                encoded = encode_mp4(work, out_video) or self._copy_media(work, out_video)
            elif not transform_failed:
                encoded = out_video if out_video.is_file() else None
            else:
                encoded = None

            if encoded is not None and encoded.is_file():
                plan.encoded = True
                plan.output_path = str(encoded)
                ops.append(RenderOp(name="encode_mp4", detail=str(encoded)))
                messages.append(f"[{self.name}] Encoded {encoded}")

                vo_path = self._voice_audio_path(voice_pack)
                if vo_path is not None:
                    muxed = renders / "_vo_muxed.mp4"
                    synced = sync_voice_to_video(encoded, vo_path, muxed)
                    if synced is not None and synced.is_file():
                        final = self._copy_media(synced, out_video) or synced
                        if final is not None and final.is_file():
                            if final.resolve() != out_video.resolve():
                                copied = self._copy_media(final, out_video)
                                if copied is not None:
                                    final = copied
                            plan.output_path = str(out_video if out_video.is_file() else final)
                            plan.encoded = True
                            ops.append(
                                RenderOp(
                                    name="sync_voice",
                                    detail=str(vo_path),
                                )
                            )
                            messages.append(
                                f"[{self.name}] Muxed VO {vo_path}"
                            )
                            try:
                                muxed.unlink(missing_ok=True)
                            except OSError:
                                pass
                    else:
                        notes_parts.append("VO mux soft-failed.")
            else:
                plan.encoded = False
                plan.output_path = ""
                plan.skipped = True
                notes_parts.append("Final encode soft-failed.")
                messages.append(f"[{self.name}] Encode soft-skipped.")

            if plan.encoded:
                thumb = extract_thumbnail(plan.output_path, out_thumb)
                if thumb is not None:
                    plan.thumbnail_path = str(thumb)
                    ops.append(RenderOp(name="extract_thumbnail", detail=str(thumb)))
                    messages.append(f"[{self.name}] Thumbnail {thumb}")
                else:
                    plan.thumbnail_path = ""
                    notes_parts.append("Thumbnail soft-failed.")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Render compose error: %s", exc)
            plan.encoded = False
            notes_parts.append(f"Compose error: {exc}")
            messages.append(f"[{self.name}] Encode soft-skipped ({exc}).")

        # Honesty: encoded only when file exists AND validates as playable video
        if plan.encoded:
            out_path = Path(plan.output_path) if plan.output_path else out_video
            validation = validate_video(out_path)
            if not validation.ok:
                # Encode was attempted; do not mark skipped (that means plan-only /
                # never tried). Downstream quality must see a failed encode.
                plan.encoded = False
                plan.output_path = ""
                plan.skipped = False
                notes_parts.append(
                    f"Full video generation failed. Stage: Render. Reason: {validation.reason}"
                )
                messages.append(
                    f"[{self.name}] Full video generation failed. "
                    f"Stage: Render. Reason: {validation.reason}"
                )
            else:
                # Package into final/final.mp4
                final_dir = root / "final"
                final_dir.mkdir(parents=True, exist_ok=True)
                packaged = final_dir / "final.mp4"
                try:
                    if out_path.resolve() != packaged.resolve():
                        shutil.copy2(out_path, packaged)
                    if packaged.is_file():
                        plan.output_path = str(packaged.resolve())
                except OSError:
                    pass

        plan.ops = ops
        plan.notes = " ".join(notes_parts) if notes_parts else (
            "Rendered final.mp4" if plan.encoded else "Encode incomplete."
        )
        pack.plan = plan
        pack.notes = plan.notes
        path = self._write_pack(project_id, root, pack)
        logger.info(
            "RenderAgent ready project_id=%s encoded=%s",
            project_id,
            plan.encoded,
        )
        return RenderResult(
            render_pack=pack, render_path=str(path), messages=messages
        )

    def _resolve_target(
        self,
        reframe_pack: dict[str, Any] | None,
        platform_pack: dict[str, Any] | None,
        job_config: VideoJobConfig,
    ) -> tuple[int, int, str]:
        aspect = "9:16"
        tw, th = 1080, 1920
        if isinstance(reframe_pack, dict):
            plan = reframe_pack.get("plan") or {}
            if isinstance(plan, dict):
                if plan.get("target_aspect"):
                    aspect = str(plan["target_aspect"])
                try:
                    ow = int(plan.get("output_width") or 0)
                    oh = int(plan.get("output_height") or 0)
                    if ow > 0 and oh > 0:
                        tw, th = ow, oh
                except (TypeError, ValueError):
                    pass
        if isinstance(platform_pack, dict):
            pplan = platform_pack.get("plan") or {}
            meta = pplan.get("metadata") if isinstance(pplan, dict) else {}
            hints = pplan.get("export_hints") if isinstance(pplan, dict) else {}
            if isinstance(meta, dict) and meta.get("aspect_recommendation"):
                aspect = str(meta["aspect_recommendation"])
                tw, th = _aspect_dims(aspect)
            if isinstance(hints, dict) and hints.get("preferred_aspect"):
                aspect = str(hints["preferred_aspect"])
                tw, th = _aspect_dims(aspect)
        if getattr(job_config, "reframe_aspect", None):
            aspect = str(job_config.reframe_aspect) or aspect
            tw, th = _aspect_dims(aspect)
        # If dims still default, derive from aspect
        if tw == 1080 and th == 1920:
            tw, th = _aspect_dims(aspect)
        return tw, th, aspect

    def _resolve_source(
        self,
        root: Path,
        meta: ProjectMetadata,
        reframe_pack: dict[str, Any] | None,
        captions_pack: dict[str, Any] | None,
        source_metadata: dict[str, Any] | None,
        speech_transcript: dict[str, Any] | None,
    ) -> Path | None:
        if isinstance(reframe_pack, dict):
            plan = reframe_pack.get("plan") or {}
            if isinstance(plan, dict) and plan.get("encoded") and plan.get("output_path"):
                p = Path(str(plan["output_path"]))
                if p.is_file():
                    return p
        if isinstance(captions_pack, dict):
            burned = str(captions_pack.get("burned_in_path") or "").strip()
            if burned and Path(burned).is_file():
                return Path(burned)
            plan = captions_pack.get("plan") or {}
            if isinstance(plan, dict) and plan.get("burn_in_applied"):
                cand = root / "captions" / "burned_in.mp4"
                if cand.is_file():
                    return cand

        for candidate in (
            root / "renders" / "reframed.mp4",
            root / "captions" / "burned_in.mp4",
        ):
            if candidate.is_file():
                return candidate

        if isinstance(speech_transcript, dict):
            mp = str(speech_transcript.get("media_path") or "").strip()
            if mp and Path(mp).is_file():
                return Path(mp)
        if isinstance(source_metadata, dict):
            for key in ("local_path", "media_path", "path", "file_path"):
                mp = str(source_metadata.get(key) or "").strip()
                if mp and Path(mp).is_file():
                    return Path(mp)
        sp = str(getattr(meta, "source_path", "") or "").strip()
        if sp and Path(sp).is_file():
            return Path(sp)
        return None

    def _caption_burn_info(
        self,
        captions_pack: dict[str, Any] | None,
        platform_pack: dict[str, Any] | None,
    ) -> tuple[bool, str]:
        burn = False
        caption_path = ""
        if isinstance(captions_pack, dict):
            plan = captions_pack.get("plan") or {}
            if isinstance(plan, dict):
                burn = bool(plan.get("burn_in_requested"))
            for key in ("ass_path", "srt_path", "vtt_path"):
                p = str(captions_pack.get(key) or "").strip()
                if p and Path(p).is_file():
                    caption_path = p
                    break
            # Already burned into source — skip re-burn
            if captions_pack.get("burned_in_path") and Path(
                str(captions_pack["burned_in_path"])
            ).is_file():
                if isinstance(plan, dict) and plan.get("burn_in_applied"):
                    burn = False
        if isinstance(platform_pack, dict):
            pplan = platform_pack.get("plan") or {}
            hints = pplan.get("export_hints") if isinstance(pplan, dict) else {}
            if isinstance(hints, dict) and hints.get("caption_burn_in") and caption_path:
                burn = True
        return burn, caption_path

    @staticmethod
    def _voice_audio_path(voice_pack: dict[str, Any] | None) -> Path | None:
        if not isinstance(voice_pack, dict):
            return None
        plan = voice_pack.get("plan") or {}
        if not isinstance(plan, dict):
            return None
        if plan.get("preserve_original", True):
            return None
        for key in ("primary_audio_path", "audio_path"):
            p = str(plan.get(key) or "").strip()
            if p and Path(p).is_file():
                return Path(p)
        return None

    def _apply_clips(
        self,
        media: Path,
        clips: dict[str, Any] | None,
        renders: Path,
        *,
        features: FeatureFlags | dict[str, Any] | None = None,
        target_width: int = 1080,
        target_height: int = 1920,
    ) -> tuple[Path, list[RenderOp], list[Path], list[str]]:
        ops: list[RenderOp] = []
        short_paths: list[Path] = []
        short_errors: list[str] = []
        if not isinstance(clips, dict):
            return media, ops, short_paths, short_errors
        items = clips.get("clips") or []
        if not isinstance(items, list) or not items:
            return media, ops, short_paths, short_errors

        multi = False
        if isinstance(features, FeatureFlags):
            multi = bool(features.multi_shorts_export)
        elif isinstance(features, dict):
            multi = bool(features.get("multi_shorts_export"))
        multi = multi or bool(clips.get("multi_shorts"))

        shorts_dir = renders / "shorts"
        if multi:
            shorts_dir.mkdir(parents=True, exist_ok=True)
        (renders.parent / "shorts").mkdir(parents=True, exist_ok=True)

        segments: list[Path] = []
        duration_counts: dict[int, int] = {}
        tw = target_width if target_width > 0 else 1080
        th = target_height if target_height > 0 else 1920

        for i, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            try:
                start = float(item.get("start") or 0.0)
                end = float(item.get("end") or 0.0)
            except (TypeError, ValueError):
                continue
            if end <= start:
                continue
            seg = renders / f"_clip_{i:03d}.mp4"
            cut = cut_segment(media, seg, start=start, end=end)
            if cut is None:
                if multi:
                    short_errors.append(
                        f"clip_{i:03d}: cut_segment failed ({start:.2f}-{end:.2f})"
                    )
                continue
            segments.append(cut)
            ops.append(
                RenderOp(name="cut_segment", detail=f"{start:.2f}-{end:.2f}")
            )

            if multi:
                try:
                    td = int(round(float(item.get("target_duration") or (end - start))))
                except (TypeError, ValueError):
                    td = int(round(end - start))
                for bucket in (10, 15, 30, 40, 45, 60, 90):
                    if abs(td - bucket) <= 5:
                        td = bucket
                        break
                idx = duration_counts.get(td, 0)
                duration_counts[td] = idx + 1
                short_name = f"short_{td}s_{idx:02d}.mp4"
                short_dst = shorts_dir / short_name
                packaged = self._package_short(
                    cut,
                    short_dst,
                    width=tw,
                    height=th,
                )
                if packaged is not None and packaged.is_file():
                    short_paths.append(packaged)
                    # Mirror under project shorts/
                    mirror = renders.parent / "shorts" / short_name
                    try:
                        shutil.copy2(packaged, mirror)
                    except OSError:
                        pass
                    ops.append(
                        RenderOp(
                            name="export_short",
                            detail=f"{short_name} {start:.2f}-{end:.2f} {tw}x{th}",
                        )
                    )
                else:
                    short_errors.append(
                        f"{short_name}: vertical encode/validation failed"
                    )

        if not segments:
            return media, ops, short_paths, short_errors
        joined = renders / "_joined.mp4"
        result = concat_segments(segments, joined)
        if result is not None:
            ops.append(RenderOp(name="concat_segments", detail=str(len(segments))))
            return result, ops, short_paths, short_errors
        return media, ops, short_paths, short_errors

    def _package_short(
        self,
        cut: Path,
        dest: Path,
        *,
        width: int,
        height: int,
    ) -> Path | None:
        """Encode a cut segment to vertical MP4 and validate (no rename-only)."""
        tmp = dest.with_suffix(".tmp.mp4")
        encoded = encode_mp4(cut, tmp, width=width, height=height)
        if encoded is None or not encoded.is_file():
            # Fallback: resize then copy
            resized = dest.with_suffix(".resized.mp4")
            r = resize(cut, resized, width=width, height=height)
            if r is None:
                return None
            encoded = encode_mp4(r, tmp) or self._copy_media(r, tmp)
            try:
                resized.unlink(missing_ok=True)
            except OSError:
                pass
        if encoded is None or not encoded.is_file():
            return None
        try:
            if dest.exists():
                dest.unlink()
            encoded.replace(dest)
        except OSError:
            copied = self._copy_media(encoded, dest)
            if copied is None:
                return None
        validation = validate_video(dest)
        if not validation.ok:
            try:
                dest.unlink(missing_ok=True)
            except OSError:
                pass
            return None
        return dest

    def _copy_media(self, src: Path, dst: Path) -> Path | None:
        try:
            shutil.copy2(src, dst)
            return dst if dst.is_file() else None
        except OSError:
            return None

    def _apply_selective_transform(
        self,
        media: Path,
        transform_intent_pack: dict[str, Any] | None,
        scenes: dict[str, Any] | None,
        renders: Path,
        *,
        voice_pack: dict[str, Any] | None = None,
        project_dir: Path | None = None,
    ) -> tuple[Path | None, list[RenderOp], dict[str, Any]]:
        from schemas.transform_intent import TransformIntent
        from tools.transform.selective import apply_selective_transform

        empty: dict[str, Any] = {"applied": False}
        if not isinstance(transform_intent_pack, dict):
            return None, [], empty
        plan = transform_intent_pack.get("plan") or {}
        if not isinstance(plan, dict) or plan.get("skipped"):
            return None, [], empty
        intent_raw = plan.get("intent") or {}
        if not isinstance(intent_raw, dict):
            return None, [], empty
        try:
            intent = TransformIntent.model_validate(intent_raw)
        except Exception:  # noqa: BLE001
            return None, [], empty
        if not intent.instruction and not intent.requested_changes:
            return None, [], empty
        vo = self._voice_audio_path(voice_pack)
        return apply_selective_transform(
            media,
            intent=intent,
            scenes=scenes if isinstance(scenes, dict) else None,
            renders=renders,
            voice_audio=vo,
            project_dir=project_dir,
        )

    def _export_transform_short(
        self,
        media: Path | None,
        renders: Path,
        *,
        features: FeatureFlags | dict[str, Any] | None,
        start: float,
        end: float,
        source_media: Path | None = None,
    ) -> list[Path]:
        multi = False
        if isinstance(features, FeatureFlags):
            multi = bool(features.multi_shorts_export)
        elif isinstance(features, dict):
            multi = bool(features.get("multi_shorts_export"))
        if not multi or end <= start:
            return []
        src = source_media if source_media and source_media.is_file() else media
        if src is None or not src.is_file():
            return []
        shorts_dir = renders / "shorts"
        shorts_dir.mkdir(parents=True, exist_ok=True)
        td = int(round(end - start))
        for bucket in (10, 15, 30, 40, 45, 60, 90):
            if abs(td - bucket) <= 5:
                td = bucket
                break
        if td < 5:
            td = 30
            end = start + td
        dest = shorts_dir / f"short_{td}s_00.mp4"
        if dest.is_file() and validate_video(dest).ok:
            return [dest]
        cut_tmp = shorts_dir / f"_transform_cut_{td}s.mp4"
        cut = cut_segment(src, cut_tmp, start=start, end=min(end, start + float(td)))
        if cut is None or not cut.is_file():
            return []
        packaged = self._package_short(cut, dest, width=1080, height=1920)
        if packaged is not None and packaged.is_file():
            return [packaged]
        return []

    def _coerce_project(
        self, project: ProjectMetadata | dict[str, Any]
    ) -> ProjectMetadata:
        if isinstance(project, ProjectMetadata):
            return project
        try:
            return ProjectMetadata.model_validate(project)
        except Exception as exc:  # noqa: BLE001
            raise RenderAgentError(f"Invalid project metadata: {exc}") from exc

    def _coerce_config(
        self, config: VideoJobConfig | dict[str, Any] | None
    ) -> VideoJobConfig:
        if config is None:
            return VideoJobConfig()
        if isinstance(config, VideoJobConfig):
            return config
        try:
            return VideoJobConfig.model_validate(config)
        except Exception as exc:  # noqa: BLE001
            raise RenderAgentError(f"Invalid job config: {exc}") from exc

    def _write_pack(
        self, project_id: str, root: Path, pack: RenderPack
    ) -> Path:
        try:
            ensure_project_analysis_dir(project_id)
        except Exception:  # noqa: BLE001
            pass
        path = root / "analysis" / "render_plan.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_text(
                json.dumps(pack.model_dump(mode="json"), indent=2),
                encoding="utf-8",
            )
            # Also mirror via core path when possible
            try:
                alt = get_render_plan_path(project_id)
                if alt.resolve() != path.resolve():
                    alt.parent.mkdir(parents=True, exist_ok=True)
                    alt.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            except Exception:  # noqa: BLE001
                pass
        except OSError as exc:
            raise StorageError(f"Failed to write render plan: {exc}") from exc
        return path
