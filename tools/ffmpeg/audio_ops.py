"""Audio normalization and stream helpers."""

from __future__ import annotations

from pathlib import Path

from tools.ffmpeg.probe import probe_media
from tools.ffmpeg.runner import ok_output, run_ffmpeg


def normalize_loudness(
    media_path: str | Path,
    output_path: str | Path,
) -> Path | None:
    """Apply loudnorm when audio exists."""
    media = Path(media_path)
    out = Path(output_path)
    if not media.is_file():
        return None
    info = probe_media(media)
    if not info or not info.get("has_audio"):
        return None
    out.parent.mkdir(parents=True, exist_ok=True)
    ok = run_ffmpeg(
        [
            "-i",
            str(media.resolve()),
            "-af",
            "loudnorm=I=-16:TP=-1.5:LRA=11",
            "-c:v",
            "copy",
            str(out.resolve()),
        ]
    )
    return ok_output(out) if ok else None


def ensure_audio_stream(media_path: str | Path) -> bool:
    info = probe_media(media_path)
    return bool(info and info.get("has_audio"))


def replace_audio(
    video_path: str | Path,
    audio_path: str | Path,
    output_path: str | Path,
) -> Path | None:
    """Replace video audio with a VO track (video copy, shortest)."""
    video = Path(video_path)
    audio = Path(audio_path)
    out = Path(output_path)
    if not video.is_file() or not audio.is_file():
        return None
    out.parent.mkdir(parents=True, exist_ok=True)
    target = out
    tmp: Path | None = None
    if target.resolve() == video.resolve():
        tmp = out.with_suffix(".vo_tmp.mp4")
        target = tmp
    ok = run_ffmpeg(
        [
            "-i",
            str(video.resolve()),
            "-i",
            str(audio.resolve()),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
            str(target.resolve()),
        ]
    )
    if not ok:
        if tmp is not None and tmp.exists():
            tmp.unlink(missing_ok=True)
        return None
    if tmp is not None:
        try:
            tmp.replace(out)
        except OSError:
            return None
    return ok_output(out)


def sync_voice_to_video(
    video_path: str | Path,
    voice_path: str | Path,
    output_path: str | Path,
) -> Path | None:
    """Pad/trim VO to video duration then mux (soft-fail → None)."""
    video = Path(video_path)
    voice = Path(voice_path)
    out = Path(output_path)
    if not video.is_file() or not voice.is_file():
        return None

    info = probe_media(video)
    duration = 0.0
    if info:
        try:
            duration = float(info.get("duration") or 0.0)
        except (TypeError, ValueError):
            duration = 0.0

    out.parent.mkdir(parents=True, exist_ok=True)
    synced = out.parent / "_voice_synced.m4a"

    if duration > 0.05:
        ok = run_ffmpeg(
            [
                "-i",
                str(voice.resolve()),
                "-af",
                f"atrim=0:{duration:.3f},apad=whole_dur={duration:.3f}",
                "-c:a",
                "aac",
                str(synced.resolve()),
            ]
        )
        audio_for_mux = synced if ok and synced.is_file() else voice
    else:
        audio_for_mux = voice

    result = replace_audio(video, audio_for_mux, out)
    if synced.exists():
        try:
            synced.unlink(missing_ok=True)
        except OSError:
            pass
    return result
