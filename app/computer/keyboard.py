"""OS keyboard fallback; callers must only use it after visual/semantic verification."""
from __future__ import annotations

from typing import Protocol


class KeyboardBackend(Protocol):
    def write(self, text: str, *, interval: float = 0.0) -> None: ...
    def hotkey(self, *keys: str) -> None: ...


class Keyboard:
    def __init__(self, backend: KeyboardBackend | None = None) -> None:
        self._backend = backend or _pyautogui()

    def type_text(self, text: str, *, interval: float = 0.01) -> None:
        if not text:
            raise ValueError("Cannot type empty text")
        self._backend.write(text, interval=interval)

    def press_hotkey(self, *keys: str) -> None:
        if not keys:
            raise ValueError("At least one key is required")
        self._backend.hotkey(*keys)


def _pyautogui() -> KeyboardBackend:
    import pyautogui
    return pyautogui
