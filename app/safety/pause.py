"""Cooperative pause control for action boundaries in an active task."""
from __future__ import annotations

import asyncio
import threading


class PauseController:
    def __init__(self) -> None:
        self._resume_event = threading.Event()
        self._resume_event.set()

    def pause(self) -> None:
        self._resume_event.clear()

    def resume(self) -> None:
        self._resume_event.set()

    @property
    def paused(self) -> bool:
        return not self._resume_event.is_set()

    async def wait_until_resumed(self) -> None:
        await asyncio.to_thread(self._resume_event.wait)
