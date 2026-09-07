"""Plugin provider registry (Rule 18)."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class VideoProvider(Protocol):
    name: str

    def generate(self, prompt: str, **kwargs: Any) -> dict[str, Any]: ...


@runtime_checkable
class AvatarProvider(Protocol):
    name: str

    def render_avatar(self, script: str, **kwargs: Any) -> dict[str, Any]: ...


@runtime_checkable
class VoiceProvider(Protocol):
    name: str

    def synthesize(self, text: str, **kwargs: Any) -> dict[str, Any]: ...


@runtime_checkable
class PublishProvider(Protocol):
    name: str

    def publish(self, payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]: ...


class ProviderRegistry:
    """Simple name → provider registry for voice/video/avatar/publish adapters."""

    def __init__(self) -> None:
        self._video: dict[str, VideoProvider] = {}
        self._avatar: dict[str, AvatarProvider] = {}
        self._voice: dict[str, VoiceProvider] = {}
        self._publish: dict[str, PublishProvider] = {}

    def register_video(self, provider: VideoProvider) -> None:
        self._video[provider.name] = provider

    def register_avatar(self, provider: AvatarProvider) -> None:
        self._avatar[provider.name] = provider

    def register_voice(self, provider: VoiceProvider) -> None:
        self._voice[provider.name] = provider

    def register_publish(self, provider: PublishProvider) -> None:
        self._publish[provider.name] = provider

    def get_video(self, name: str) -> VideoProvider | None:
        return self._video.get(name)

    def get_avatar(self, name: str) -> AvatarProvider | None:
        return self._avatar.get(name)

    def get_voice(self, name: str) -> VoiceProvider | None:
        return self._voice.get(name)

    def get_publish(self, name: str) -> PublishProvider | None:
        return self._publish.get(name)

    def list_providers(self) -> dict[str, list[str]]:
        return {
            "video": sorted(self._video),
            "avatar": sorted(self._avatar),
            "voice": sorted(self._voice),
            "publish": sorted(self._publish),
        }


_REGISTRY: ProviderRegistry | None = None


def get_provider_registry() -> ProviderRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = ProviderRegistry()
        _register_builtin_adapters(_REGISTRY)
    return _REGISTRY


class _StubVoice:
    name = "local_stub"

    def synthesize(self, text: str, **kwargs: Any) -> dict[str, Any]:
        return {"provider": self.name, "text": text, "path": "", "stub": True}


class _StubVideo:
    name = "local_stub"

    def generate(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        return {"provider": self.name, "prompt": prompt, "path": "", "stub": True}


class _StubAvatar:
    name = "local_stub"

    def render_avatar(self, script: str, **kwargs: Any) -> dict[str, Any]:
        return {"provider": self.name, "script": script, "path": "", "stub": True}


class _StubPublish:
    name = "local_stub"

    def publish(self, payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return {"provider": self.name, "accepted": False, "payload": payload, "stub": True}


def _register_builtin_adapters(reg: ProviderRegistry) -> None:
    reg.register_voice(_StubVoice())
    reg.register_video(_StubVideo())
    reg.register_avatar(_StubAvatar())
    reg.register_publish(_StubPublish())
