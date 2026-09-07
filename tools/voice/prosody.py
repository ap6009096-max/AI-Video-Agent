"""Map emotion / speed / pitch into edge-tts prosody strings."""

from __future__ import annotations

from typing import Any

VOICE_EMOTIONS: frozenset[str] = frozenset(
    {"neutral", "happy", "sad", "angry", "excited", "calm", "serious"}
)

# Emotion → additive deltas on (rate_pct, pitch_hz, volume_pct) after speed/pitch base
_EMOTION_DELTAS: dict[str, tuple[float, float, float]] = {
    "neutral": (0.0, 0.0, 0.0),
    "happy": (8.0, 25.0, 5.0),
    "sad": (-12.0, -35.0, -5.0),
    "angry": (10.0, 15.0, 10.0),
    "excited": (18.0, 40.0, 8.0),
    "calm": (-10.0, -15.0, -3.0),
    "serious": (-5.0, -10.0, 0.0),
}


def clamp_factor(value: float, lo: float = 0.5, hi: float = 1.5) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        v = 1.0
    return max(lo, min(hi, v))


def normalize_emotion(emotion: str | None) -> str:
    key = (emotion or "neutral").strip().lower()
    return key if key in VOICE_EMOTIONS else "neutral"


def speed_to_rate(speed: float) -> str:
    """Map 0.5–1.5 speed multiplier to edge-tts rate like '+0%' / '-20%'."""
    factor = clamp_factor(speed)
    pct = int(round((factor - 1.0) * 100))
    if pct >= 0:
        return f"+{pct}%"
    return f"{pct}%"


def pitch_to_ssml(pitch: float) -> str:
    """Map 0.5–1.5 pitch multiplier to edge-tts pitch like '+0Hz'."""
    factor = clamp_factor(pitch)
    # 1.0 → 0Hz; each 0.1 away from 1.0 ≈ 20Hz
    hz = int(round((factor - 1.0) * 200))
    if hz >= 0:
        return f"+{hz}Hz"
    return f"{hz}Hz"


def _parse_pct(token: str) -> float:
    raw = (token or "+0%").strip().rstrip("%")
    try:
        return float(raw)
    except ValueError:
        return 0.0


def _parse_hz(token: str) -> float:
    raw = (token or "+0Hz").strip().lower().rstrip("hz")
    try:
        return float(raw)
    except ValueError:
        return 0.0


def _format_pct(value: float) -> str:
    pct = int(round(value))
    pct = max(-50, min(100, pct))
    return f"+{pct}%" if pct >= 0 else f"{pct}%"


def _format_hz(value: float) -> str:
    hz = int(round(value))
    hz = max(-100, min(100, hz))
    return f"+{hz}Hz" if hz >= 0 else f"{hz}Hz"


def build_prosody(
    *,
    emotion: str = "neutral",
    speed: float = 1.0,
    pitch: float = 1.0,
) -> dict[str, Any]:
    """Return rate/pitch/volume strings plus normalized emotion metadata."""
    emo = normalize_emotion(emotion)
    base_rate = _parse_pct(speed_to_rate(speed))
    base_pitch = _parse_hz(pitch_to_ssml(pitch))
    d_rate, d_pitch, d_vol = _EMOTION_DELTAS.get(emo, (0.0, 0.0, 0.0))
    rate = _format_pct(base_rate + d_rate)
    pitch_ssml = _format_hz(base_pitch + d_pitch)
    volume = _format_pct(d_vol)
    note = f"emotion={emo}, speed={clamp_factor(speed):.2f}, pitch={clamp_factor(pitch):.2f}"
    return {
        "emotion": emo,
        "speaking_rate": clamp_factor(speed),
        "pitch": clamp_factor(pitch),
        "rate": rate,
        "pitch_ssml": pitch_ssml,
        "volume": volume,
        "note": note,
    }
