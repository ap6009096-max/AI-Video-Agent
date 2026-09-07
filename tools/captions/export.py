"""Export caption cues to SRT, VTT, and ASS (Dynamic Caption Engine)."""

from __future__ import annotations

from pathlib import Path

from schemas.captions import (
    CaptionCue,
    CaptionStylePreset,
    CaptionTrack,
    PlatformSafeArea,
)

_MOTION_EFFECTS = frozenset({"pop", "bounce", "zoom"})
_KARAOKE_EFFECTS = frozenset({"word_highlight", "karaoke"})
_ASS_EFFECTS = _MOTION_EFFECTS | _KARAOKE_EFFECTS


def style_effects(style: CaptionStylePreset) -> set[str]:
    """Union of primary animation + effects list."""
    out: set[str] = set()
    anim = (style.animation or "none").strip().lower()
    if anim and anim != "none":
        out.add(anim)
    for item in style.effects or []:
        key = str(item or "").strip().lower()
        if key and key != "none":
            out.add(key)
    return out


def _format_srt_time(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, milli = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{milli:03d}"


def _format_vtt_time(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, milli = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{milli:03d}"


def _format_ass_time(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    cs = int(round(seconds * 100))
    h, rem = divmod(cs, 360_000)
    m, rem = divmod(rem, 6_000)
    s, c = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"


def _display_text(cue: CaptionCue) -> str:
    text = (cue.text or "").strip()
    if cue.emoji:
        text = f"{text} {cue.emoji}".strip()
    return text


def _wrap_lines(text: str, max_chars: int, max_lines: int) -> str:
    words = text.split()
    if not words:
        return text
    lines: list[str] = []
    current = ""
    for w in words:
        candidate = f"{current} {w}".strip()
        if current and len(candidate) > max_chars:
            lines.append(current)
            current = w
            if len(lines) >= max_lines:
                break
        else:
            current = candidate
    if current and len(lines) < max_lines:
        lines.append(current)
    return "\\N".join(lines) if max_lines > 1 else " ".join(lines)


def render_srt(cues: list[CaptionCue]) -> str:
    blocks: list[str] = []
    for i, cue in enumerate(cues, start=1):
        text = _display_text(cue).replace("\n", " ")
        blocks.append(
            f"{i}\n{_format_srt_time(cue.start)} --> {_format_srt_time(cue.end)}\n{text}\n"
        )
    return "\n".join(blocks).rstrip() + ("\n" if blocks else "")


def render_vtt(cues: list[CaptionCue]) -> str:
    lines = ["WEBVTT", ""]
    for cue in cues:
        text = _display_text(cue).replace("\n", " ")
        lines.append(
            f"{_format_vtt_time(cue.start)} --> {_format_vtt_time(cue.end)}"
        )
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


def _ass_style_line(style: CaptionStylePreset, safe: PlatformSafeArea) -> str:
    a = style.ass_style
    bold = -1 if a.bold else 0
    return (
        f"Style: Default,{a.font},{a.size},{a.primary_color},{a.highlight_color},"
        f"{a.outline_color},{a.back_color},{bold},0,0,0,100,100,0,0,1,"
        f"{a.outline},{a.shadow},{safe.alignment},{safe.margin_l},{safe.margin_r},"
        f"{safe.margin_v},1"
    )


def _karaoke_text(cue: CaptionCue, style: CaptionStylePreset, effects: set[str]) -> str:
    use_karaoke = bool(effects & _KARAOKE_EFFECTS) and bool(cue.words)
    if not use_karaoke:
        return _wrap_lines(
            _display_text(cue),
            style.max_chars_per_line,
            style.max_lines,
        )
    parts: list[str] = []
    for w in cue.words:
        dur_cs = max(1, int(round((w.end - w.start) * 100)))
        token = w.word
        if w.highlighted or token in cue.highlighted_tokens:
            parts.append(
                f"{{\\k{dur_cs}\\c{style.ass_style.highlight_color}}}{token}"
            )
        else:
            parts.append(f"{{\\k{dur_cs}}}{token}")
    body = " ".join(parts)
    if cue.emoji:
        body = f"{body} {cue.emoji}"
    return body


def _motion_prefix(cue: CaptionCue, effects: set[str]) -> str:
    """ASS \\t scale animations for pop / bounce / zoom."""
    tags: list[str] = []
    duration_ms = max(200, int(round((cue.end - cue.start) * 1000)))

    if "bounce" in effects:
        # Pulse up then settle within first ~400ms
        tags.append(r"{\t(0,150,\fscx125\fscy125)\t(150,350,\fscx100\fscy100)}")
    elif "pop" in effects:
        tags.append(r"{\t(0,200,\fscx120\fscy120)\t(200,400,\fscx100\fscy100)}")
    elif "zoom" in effects:
        # Zoom from 80% → 100% over cue (capped)
        end_t = min(duration_ms, 800)
        tags.append(rf"{{\fscx80\fscy80\t(0,{end_t},\fscx100\fscy100)}}")

    return "".join(tags)


def render_ass(
    track: CaptionTrack,
    style: CaptionStylePreset,
    safe: PlatformSafeArea,
) -> str:
    """Render ASS with platform-safe margins; karaoke + motion effects."""
    effects = style_effects(style)
    header = [
        "[Script Info]",
        "Title: AI Video Agent Captions",
        "ScriptType: v4.00+",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "YCbCr Matrix: None",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        _ass_style_line(style, safe),
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    events: list[str] = []
    for cue in track.cues:
        text = _karaoke_text(cue, style, effects)
        motion = _motion_prefix(cue, effects)
        if motion:
            text = motion + text
        if track.direction == "rtl":
            text = "{\\an2\\q2}" + text
        events.append(
            f"Dialogue: 0,{_format_ass_time(cue.start)},{_format_ass_time(cue.end)},"
            f"Default,,0,0,0,,{text}"
        )
    return "\n".join(header + events) + "\n"


def write_srt(path: Path, cues: list[CaptionCue]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_srt(cues), encoding="utf-8")
    return path.resolve()


def write_vtt(path: Path, cues: list[CaptionCue]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_vtt(cues), encoding="utf-8")
    return path.resolve()


def write_ass(
    path: Path,
    track: CaptionTrack,
    style: CaptionStylePreset,
    safe: PlatformSafeArea,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_ass(track, style, safe), encoding="utf-8")
    return path.resolve()


def ass_is_useful(style: CaptionStylePreset, *, burn_in: bool) -> bool:
    """ASS is useful for animated styles or when burn-in is requested."""
    if burn_in:
        return True
    return bool(style_effects(style) & _ASS_EFFECTS)
