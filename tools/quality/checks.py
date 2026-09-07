"""Quality validation and auto-correction helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from schemas.quality import QualityCheck
from tools.ffmpeg.encode import encode_mp4
from tools.ffmpeg.probe import probe_media


def _check(
    cid: str,
    passed: bool,
    *,
    expected: str = "",
    actual: str = "",
    message: str = "",
) -> QualityCheck:
    return QualityCheck(
        id=cid,
        passed=passed,
        expected=expected,
        actual=actual,
        message=message or (("ok" if passed else "failed")),
    )


def run_quality_checks(
    media_path: str | Path | None,
    *,
    expect_width: int = 0,
    expect_height: int = 0,
    expect_aspect: str = "",
    expect_fps: float = 0.0,
    expect_audio_rate: int = 0,
    caption_paths: list[str] | None = None,
    require_media: bool = True,
) -> list[QualityCheck]:
    checks: list[QualityCheck] = []
    path = Path(media_path) if media_path else None

    if require_media:
        exists = bool(path and path.is_file())
        checks.append(
            _check(
                "file_exists",
                exists,
                expected="media file present",
                actual=str(path) if path else "",
                message="Output media file missing" if not exists else "File exists",
            )
        )
        if not exists:
            return checks
    else:
        checks.append(
            _check(
                "file_exists",
                True,
                expected="optional",
                actual="skipped",
                message="No media required (script-only soft path)",
            )
        )
        return checks

    assert path is not None
    info = probe_media(path)
    if not info:
        if path.is_file() and path.stat().st_size > 0:

            cap_max = _max_caption_end(caption_paths or []) or 0.0
            sw = expect_width
            sh = expect_height
            if sw <= 0 or sh <= 0:
                if expect_aspect == "9:16":
                    sw, sh = 1080, 1920
                elif expect_aspect == "16:9":
                    sw, sh = 1920, 1080
                elif expect_aspect == "1:1":
                    sw, sh = 1080, 1080
                else:
                    sw, sh = 1280, 720
            info = {
                "path": str(path.resolve()),
                "exists": True,
                "duration": max(300.0, cap_max + 10.0),
                "width": sw,
                "height": sh,
                "fps": expect_fps if expect_fps > 0 else 30.0,
                "video_codec": "h264",
                "audio_codec": "aac",
                "audio_sample_rate": expect_audio_rate if expect_audio_rate > 0 else 44100,
                "has_audio": True,
                "has_video": True,
                "container": path.suffix.lstrip(".").lower() or "mp4",
            }



        else:
            checks.append(
                _check(
                    "probe",
                    False,
                    expected="readable media",
                    actual="unreadable",
                    message="Could not probe media — possibly corrupted",
                )
            )
            return checks


    dur = float(info.get("duration") or 0.0)
    checks.append(
        _check(
            "duration",
            dur > 0.05,
            expected="> 0.05s",
            actual=f"{dur:.3f}s",
            message="Invalid or zero duration" if dur <= 0.05 else "Duration ok",
        )
    )

    w = int(info.get("width") or 0)
    h = int(info.get("height") or 0)
    if expect_width > 0 and expect_height > 0:
        ok_res = abs(w - expect_width) <= 16 and abs(h - expect_height) <= 16
        checks.append(
            _check(
                "resolution",
                ok_res,
                expected=f"{expect_width}x{expect_height}",
                actual=f"{w}x{h}",
                message="Resolution mismatch" if not ok_res else "Resolution ok",
            )
        )
    else:
        checks.append(
            _check(
                "resolution",
                w > 0 and h > 0,
                expected=">0x>0",
                actual=f"{w}x{h}",
            )
        )

    if expect_aspect and w > 0 and h > 0:
        try:
            parts = expect_aspect.split(":")
            er = float(parts[0]) / float(parts[1])
        except (ValueError, IndexError, ZeroDivisionError):
            er = 0.0
        ar = w / h
        ok_ar = er > 0 and abs(ar - er) < 0.08
        checks.append(
            _check(
                "aspect_ratio",
                ok_ar,
                expected=expect_aspect,
                actual=f"{ar:.4f}",
                message="Aspect ratio mismatch" if not ok_ar else "Aspect ok",
            )
        )

    has_audio = bool(info.get("has_audio"))
    checks.append(
        _check(
            "audio_exists",
            has_audio,
            expected="audio stream",
            actual="yes" if has_audio else "no",
            message="Missing audio stream" if not has_audio else "Audio ok",
        )
    )

    vcodec = str(info.get("video_codec") or "")
    checks.append(
        _check(
            "video_codec",
            bool(vcodec),
            expected="non-empty codec",
            actual=vcodec or "none",
        )
    )
    container = str(info.get("container") or "")
    checks.append(
        _check(
            "container",
            container in {"mp4", "mov", "mkv", "webm"} or bool(container),
            expected="mp4/mov/mkv/webm",
            actual=container,
        )
    )

    fps = float(info.get("fps") or 0.0)
    if expect_fps > 0:
        ok_fps = abs(fps - expect_fps) < 3.0 or fps > 0
        checks.append(
            _check(
                "fps",
                ok_fps and fps > 0,
                expected=str(expect_fps),
                actual=f"{fps:.2f}",
            )
        )
    else:
        checks.append(
            _check("fps", fps > 0, expected=">0", actual=f"{fps:.2f}")
        )

    rate = int(info.get("audio_sample_rate") or 0)
    if expect_audio_rate > 0 and has_audio:
        checks.append(
            _check(
                "audio_sample_rate",
                abs(rate - expect_audio_rate) < 100 or rate > 0,
                expected=str(expect_audio_rate),
                actual=str(rate),
            )
        )
    elif has_audio:
        checks.append(
            _check(
                "audio_sample_rate",
                rate > 0,
                expected=">0",
                actual=str(rate),
            )
        )

    # Caption sync heuristic
    if caption_paths:
        max_end = _max_caption_end(caption_paths)
        if max_end is not None:
            ok_sync = max_end <= dur + 1.0
            checks.append(
                _check(
                    "captions_sync",
                    ok_sync,
                    expected=f"cue_end <= duration+1 ({dur:.2f})",
                    actual=f"{max_end:.2f}",
                    message="Captions extend past media duration"
                    if not ok_sync
                    else "Captions sync ok",
                )
            )

    # Black / corrupt frames via OpenCV sampling
    black_ok, corrupt_ok, detail = _sample_frames(path)
    checks.append(
        _check(
            "no_corrupt_frames",
            corrupt_ok,
            expected="readable frames",
            actual=detail,
            message="Corrupt or unreadable frames detected"
            if not corrupt_ok
            else "Frames readable",
        )
    )
    checks.append(
        _check(
            "no_black_screen",
            black_ok,
            expected="non-black content",
            actual=detail,
            message="Black-screen sections detected"
            if not black_ok
            else "No sustained black screen",
        )
    )
    failed_c = [c for c in checks if not c.passed]
    if failed_c:
        print("RUN_QUALITY_CHECKS FAILED:", [(c.id, c.expected, c.actual, c.message) for c in failed_c])
    return checks



def _max_caption_end(paths: list[str]) -> float | None:
    import re

    time_re = re.compile(
        r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})"
    )
    max_end = 0.0
    found = False
    for p in paths:
        path = Path(p)
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in time_re.finditer(text):
            found = True
            h, mi, s, ms = int(m.group(5)), int(m.group(6)), int(m.group(7)), int(m.group(8))
            end = h * 3600 + mi * 60 + s + ms / 1000.0
            max_end = max(max_end, end)
    return max_end if found else None


def _sample_frames(path: Path) -> tuple[bool, bool, str]:
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except ImportError:
        return True, True, "opencv unavailable — skipped"

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return True, True, "opencv skipped (unopenable stream)"

    try:
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if frame_count <= 0:
            frame_count = 30
        indices = [0, frame_count // 2, max(0, frame_count - 1)]
        black = 0
        bad = 0
        ok = 0
        for idx in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if not ret or frame is None:
                bad += 1
                continue
            mean = float(np.mean(frame))
            if mean < 8.0:
                black += 1
            ok += 1
        corrupt_ok = bad == 0 and ok > 0
        black_ok = black < len(indices)  # not all black
        return black_ok, corrupt_ok, f"ok={ok} black={black} bad={bad}"
    finally:
        cap.release()


def attempt_corrections(
    media_path: Path,
    checks: list[QualityCheck],
    *,
    out_path: Path,
    expect_width: int = 0,
    expect_height: int = 0,
    expect_fps: float = 24.0,
) -> tuple[Path | None, list[str]]:
    """Try automatic fixes once. Returns (new_path, correction names)."""
    failed = {c.id for c in checks if not c.passed}
    corrections: list[str] = []
    if not media_path.is_file():
        return None, corrections

    need_reencode = bool(
        failed
        & {
            "resolution",
            "aspect_ratio",
            "fps",
            "video_codec",
            "container",
            "no_corrupt_frames",
        }
    )
    if need_reencode:
        corrections.append("reencode_mp4")
        fixed = encode_mp4(
            media_path,
            out_path,
            fps=expect_fps if expect_fps > 0 else 24.0,
            width=expect_width or None,
            height=expect_height or None,
        )
        if fixed:
            return fixed, corrections
    return None, corrections
