"""Reference voice analyzer — match an uploaded audio sample to an edge-tts voice profile.

This does NOT perform voice cloning.  It estimates basic acoustic characteristics
(pitch, speaking rate, gender heuristic) from a short audio sample and returns
a VoiceProfile that the VoiceAgent uses to pick the closest edge-tts voice and
SSML parameters (rate, pitch).
"""

from __future__ import annotations

import io
import math
from pathlib import Path
from typing import Union


class VoiceProfile:
    """Estimated voice characteristics from a reference audio clip."""

    def __init__(
        self,
        *,
        gender: str = "neutral",          # "male" | "female" | "neutral"
        pitch_hz: float = 150.0,           # estimated fundamental frequency
        pitch_ssml: str = "+0Hz",          # SSML pitch adjustment string
        rate: str = "+0%",                 # SSML rate adjustment string
        speaking_rate_wpm: float = 130.0,  # estimated words per minute
        energy_db: float = -20.0,          # estimated RMS dB
        notes: str = "",
    ) -> None:
        self.gender = gender
        self.pitch_hz = pitch_hz
        self.pitch_ssml = pitch_ssml
        self.rate = rate
        self.speaking_rate_wpm = speaking_rate_wpm
        self.energy_db = energy_db
        self.notes = notes

    def to_dict(self) -> dict:
        return {
            "gender": self.gender,
            "pitch_hz": self.pitch_hz,
            "pitch_ssml": self.pitch_ssml,
            "rate": self.rate,
            "speaking_rate_wpm": self.speaking_rate_wpm,
            "energy_db": self.energy_db,
            "notes": self.notes,
        }


def analyze_reference_voice(
    source: Union[str, Path, bytes, io.IOBase],
) -> VoiceProfile:
    """Analyze a reference audio file and return a VoiceProfile.

    Attempts numpy/scipy-based analysis when available, otherwise returns
    a safe neutral default.

    Args:
        source: Path, bytes, or file-like object for the audio file.

    Returns:
        VoiceProfile with estimated characteristics.
    """
    raw, ext = _load_raw(source)
    if not raw:
        return VoiceProfile(notes="No audio data — using neutral default.")

    try:
        return _analyze_numpy(raw, ext)
    except Exception as exc:  # noqa: BLE001
        return VoiceProfile(notes=f"Analysis skipped ({exc}) — using neutral default.")


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _load_raw(source: Union[str, Path, bytes, io.IOBase]) -> tuple[bytes, str]:
    ext = ""
    if isinstance(source, (str, Path)):
        p = Path(source)
        ext = p.suffix.lower()
        try:
            return p.read_bytes(), ext
        except OSError:
            return b"", ext
    elif isinstance(source, (bytes, bytearray)):
        return bytes(source), ext
    elif hasattr(source, "read"):
        name = getattr(source, "name", "") or ""
        ext = Path(name).suffix.lower()
        try:
            data = source.read()
            if isinstance(data, str):
                data = data.encode()
            return data, ext
        except Exception:  # noqa: BLE001
            return b"", ext
    return b"", ext


def _analyze_numpy(raw: bytes, ext: str) -> VoiceProfile:
    """Use numpy + wave/audioop for lightweight pitch/energy estimation."""
    import wave
    import struct
    import array as arr

    # Try to read as WAV; for other formats degrade gracefully
    samples: list[float] = []
    sample_rate = 16000

    if ext in (".wav", "") or ext == "":
        try:
            with wave.open(io.BytesIO(raw)) as wf:
                sample_rate = wf.getframerate()
                n_frames = wf.getnframes()
                n_ch = wf.getnchannels()
                sw = wf.getsampwidth()
                raw_samples = wf.readframes(min(n_frames, sample_rate * 10))  # max 10s
                if sw == 2:
                    unpacked = struct.unpack(f"<{len(raw_samples)//2}h", raw_samples)
                    # Mix to mono
                    if n_ch > 1:
                        unpacked = tuple(unpacked[i] for i in range(0, len(unpacked), n_ch))
                    samples = [s / 32768.0 for s in unpacked]
        except Exception:  # noqa: BLE001
            pass

    if not samples:
        # Cannot decode — return neutral
        return VoiceProfile(notes=f"Could not decode audio ({ext}) — using neutral default.")

    # RMS energy
    rms = math.sqrt(sum(s * s for s in samples) / len(samples)) if samples else 1e-9
    energy_db = 20 * math.log10(max(rms, 1e-9))

    # Zero-crossing rate — crude pitch proxy
    zcr = sum(
        1 for i in range(1, len(samples)) if (samples[i] >= 0) != (samples[i - 1] >= 0)
    ) / (len(samples) / sample_rate)

    # ZCR heuristic: male voice ~60–150 Hz fundamental → lower ZCR
    # female voice ~150–300 Hz → higher ZCR (very rough)
    estimated_pitch_hz = max(60.0, min(zcr / 4.0, 400.0))

    if estimated_pitch_hz < 140:
        gender = "male"
    elif estimated_pitch_hz > 200:
        gender = "female"
    else:
        gender = "neutral"

    # SSML pitch: centre at 150 Hz
    pitch_delta_st = 12 * math.log2(max(estimated_pitch_hz, 60) / 150)
    if abs(pitch_delta_st) < 1:
        pitch_ssml = "+0Hz"
    elif pitch_delta_st > 0:
        pitch_ssml = f"+{int(pitch_delta_st * 10)}Hz"
    else:
        pitch_ssml = f"{int(pitch_delta_st * 10)}Hz"

    # Speaking rate heuristic from energy envelope — crude but fast
    # Default 130 wpm; if audio is very dense, bump up slightly
    speaking_rate_wpm = 130.0
    if energy_db > -15:
        speaking_rate_wpm = 145.0
    elif energy_db < -30:
        speaking_rate_wpm = 110.0

    rate_pct = int((speaking_rate_wpm - 130) / 130 * 100)
    rate_ssml = f"+{rate_pct}%" if rate_pct >= 0 else f"{rate_pct}%"

    return VoiceProfile(
        gender=gender,
        pitch_hz=round(estimated_pitch_hz, 1),
        pitch_ssml=pitch_ssml,
        rate=rate_ssml,
        speaking_rate_wpm=round(speaking_rate_wpm, 1),
        energy_db=round(energy_db, 1),
        notes=(
            f"Estimated from {len(samples)} samples @ {sample_rate}Hz. "
            "Not voice cloning — nearest edge-tts voice selected."
        ),
    )
