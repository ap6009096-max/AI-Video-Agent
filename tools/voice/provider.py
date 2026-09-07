"""TTS provider abstraction — passthrough or edge-tts."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Protocol

from core.logging import get_logger
from schemas.av_plan import VoicePlan

logger = get_logger(__name__)


class TTSProvider(Protocol):
    name: str

    def is_available(self) -> bool: ...

    def synthesize(
        self,
        text: str,
        *,
        voice_plan: VoicePlan,
        out_path: Path,
    ) -> Path | None: ...


class PassthroughTTSProvider:
    """No-op provider: never writes audio; callers must preserve original."""

    name = "passthrough"

    def is_available(self) -> bool:
        return True

    def synthesize(
        self,
        text: str,
        *,
        voice_plan: VoicePlan,
        out_path: Path,
    ) -> Path | None:
        _ = (text, voice_plan, out_path)
        return None


class EdgeTTSProvider:
    """Microsoft Edge neural TTS via the edge-tts package."""

    name = "edge"

    def is_available(self) -> bool:
        try:
            import edge_tts  # noqa: F401

            return True
        except ImportError:
            return False

    def synthesize(
        self,
        text: str,
        *,
        voice_plan: VoicePlan,
        out_path: Path,
    ) -> Path | None:
        cleaned = (text or "").strip()
        if not cleaned:
            return None
        if not self.is_available():
            return None
        voice = (
            voice_plan.provider_voice_id
            or "en-US-JennyNeural"
        ).strip()
        rate = (voice_plan.rate or "+0%").strip()
        pitch = (voice_plan.pitch_ssml or "+0Hz").strip()
        volume = (voice_plan.volume or "+0%").strip()
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            asyncio.run(
                self._save(cleaned, voice, rate, pitch, volume, out)
            )
        except RuntimeError:
            # Nested event loop — use a fresh loop
            try:
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(
                        self._save(cleaned, voice, rate, pitch, volume, out)
                    )
                finally:
                    loop.close()
            except Exception as exc:  # noqa: BLE001
                logger.warning("edge-tts synthesize failed: %s", exc)
                return None
        except Exception as exc:  # noqa: BLE001
            logger.warning("edge-tts synthesize failed: %s", exc)
            return None
        return out if out.is_file() and out.stat().st_size > 0 else None

    @staticmethod
    async def _save(
        text: str,
        voice: str,
        rate: str,
        pitch: str,
        volume: str,
        out: Path,
    ) -> None:
        import edge_tts

        communicate = edge_tts.Communicate(
            text,
            voice,
            rate=rate,
            pitch=pitch,
            volume=volume,
        )
        await communicate.save(str(out))


def get_tts_provider() -> TTSProvider:
    """Return configured TTS provider, or passthrough when unset/unknown."""
    from config.settings import get_settings

    settings = get_settings()
    raw = (settings.tts_provider or "").strip().lower()
    if not raw or raw in {"passthrough", "none", "null"}:
        return PassthroughTTSProvider()
    if raw in {"edge", "edge-tts", "edgetts"}:
        provider = EdgeTTSProvider()
        if provider.is_available():
            return provider
        logger.warning("TTS_PROVIDER=edge but edge-tts is not installed")
        return PassthroughTTSProvider()
    # Unknown names fall back to passthrough so jobs never invent audio.
    return PassthroughTTSProvider()
