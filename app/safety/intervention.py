"""Manual-login/security-challenge coordination without bypassing provider controls."""
from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable

from app.safety.emergency_stop import EmergencyStop


class UserInterventionGate:
    """Pauses the runtime until the account owner confirms a page is ready."""

    def __init__(self, notify: Callable[[str], None] | None = None) -> None:
        self._ready = threading.Event()
        self._notify = notify or (lambda _: None)

    def continue_run(self) -> None:
        self._ready.set()

    async def wait(self, message: str, emergency_stop: EmergencyStop) -> None:
        self._ready.clear()
        self._notify(message)
        while not self._ready.is_set():
            emergency_stop.raise_if_triggered()
            await asyncio.sleep(0.2)


class ConsoleInterventionGate(UserInterventionGate):
    """CLI implementation that waits for an explicit Enter after manual work."""

    async def wait(self, message: str, emergency_stop: EmergencyStop) -> None:
        print(f"\nManual action required: {message}\nComplete it in Chrome, then press Enter to continue.")
        await asyncio.to_thread(input)
        emergency_stop.raise_if_triggered()
