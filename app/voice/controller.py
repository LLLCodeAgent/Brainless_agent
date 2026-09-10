"""Write-only credential and lifecycle control plane for dashboard voice setup."""
from __future__ import annotations
import asyncio
from collections.abc import Callable

from app.voice.config import VoiceConfig
from app.voice.service import VoiceService


class VoiceControlPlane:
    """Owns VoiceService lifecycle; API keys are held in memory and never projected."""
    def __init__(self, factory: Callable[[VoiceConfig], VoiceService]) -> None:
        self._factory = factory
        self._service: VoiceService | None = None
        self._listener: asyncio.Task[None] | None = None
        self._running = False

    def configure(self, api_key: str, settings: dict[str, object] | None = None) -> None:
        if self.health_check():
            raise ValueError("Stop voice before changing its configuration")
        if not 16 <= len(api_key.strip()) <= 512:
            raise ValueError("AssemblyAI API key length is invalid")
        settings = settings or {}
        allowed = {"model", "language", "idle_timeout", "max_session_duration",
                   "min_confidence", "sensitive_confidence"}
        unknown = set(settings) - allowed
        if unknown: raise ValueError("Unsupported voice configuration field")
        config = VoiceConfig(api_key.strip(), **settings)
        config.validate()
        self._service = self._factory(config)

    def configure_config(self, config: VoiceConfig) -> None:
        """Install validated trusted startup configuration without exposing its key."""
        if self.health_check():
            raise ValueError("Stop voice before changing its configuration")
        config.validate()
        self._service = self._factory(config)

    async def start(self) -> None:
        if self._service is None: raise ValueError("Configure AssemblyAI before starting voice")
        if self._running: return
        await self._service.start()
        self._running = True
        if not self._listener or self._listener.done():
            self._listener = asyncio.create_task(self._service.listen(), name="voice-microphone")

    async def stop(self) -> None:
        if self._listener:
            self._listener.cancel()
            await asyncio.gather(self._listener, return_exceptions=True)
            self._listener = None
        if self._service and self._running: await self._service.stop()
        self._running = False

    def health_check(self) -> bool:
        return bool(self._service and self._service.health_check())

    def snapshot(self) -> dict[str, object]:
        if self._service: return {**self._service.snapshot(), "configured": True}
        return {"status": "not_configured", "connection": "disconnected", "history": [],
                "current_transcript": "", "final_transcript": "", "error": None,
                "configured": False}
