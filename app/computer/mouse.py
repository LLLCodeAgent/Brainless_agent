"""OS mouse fallback, intentionally separate from DOM-first provider interaction."""
from __future__ import annotations

from typing import Protocol


class MouseBackend(Protocol):
    def click(self, x: int, y: int, *, clicks: int = 1, button: str = "left") -> None: ...


class Mouse:
    def __init__(self, backend: MouseBackend | None = None) -> None:
        self._backend = backend or _pyautogui()

    def click(self, x: int, y: int, *, clicks: int = 1, button: str = "left") -> None:
        if x < 0 or y < 0:
            raise ValueError("Screen coordinates must be non-negative")
        self._backend.click(x, y, clicks=clicks, button=button)


def _pyautogui() -> MouseBackend:
    import pyautogui
    return pyautogui
