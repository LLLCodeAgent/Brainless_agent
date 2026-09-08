"""Cooperative emergency-stop latch usable by UI and future global-hotkey adapters."""
from __future__ import annotations

import threading


class EmergencyStop:
    """Thread-safe stop latch; callers must check it before each external action."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def trigger(self) -> None:
        self._event.set()

    def clear(self) -> None:
        self._event.clear()

    @property
    def triggered(self) -> bool:
        return self._event.is_set()

    def raise_if_triggered(self) -> None:
        if self.triggered:
            raise EmergencyStopRequested("Emergency stop requested")


class EmergencyStopRequested(RuntimeError):
    pass
