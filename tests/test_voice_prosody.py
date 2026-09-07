"""Tests for voice prosody mapping."""

from __future__ import annotations

from tools.voice.prosody import build_prosody, pitch_to_ssml, speed_to_rate


def test_speed_to_rate() -> None:
    assert speed_to_rate(1.0) == "+0%"
    assert speed_to_rate(1.2).startswith("+")
    assert speed_to_rate(0.8).startswith("-")


def test_pitch_to_ssml() -> None:
    assert pitch_to_ssml(1.0) == "+0Hz"
    assert "Hz" in pitch_to_ssml(1.2)
    assert pitch_to_ssml(0.7).startswith("-")


def test_emotion_shifts_prosody() -> None:
    neutral = build_prosody(emotion="neutral", speed=1.0, pitch=1.0)
    excited = build_prosody(emotion="excited", speed=1.0, pitch=1.0)
    sad = build_prosody(emotion="sad", speed=1.0, pitch=1.0)
    assert neutral["emotion"] == "neutral"
    assert excited["rate"] != sad["rate"] or excited["pitch_ssml"] != sad["pitch_ssml"]
    assert excited["emotion"] == "excited"
