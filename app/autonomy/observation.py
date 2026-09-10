"""Pluggable screen-understanding boundary for computer-control backends."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

@dataclass(frozen=True, slots=True)
class ScreenElement:
    role: str
    label: str
    bounds: tuple[int, int, int, int] | None = None
    confidence: float = 0.0
    metadata: dict[str, str] = field(default_factory=dict)

@dataclass(frozen=True, slots=True)
class ScreenObservation:
    screenshot_reference: str | None = None
    elements: tuple[ScreenElement, ...] = ()
    text: tuple[str, ...] = ()
    active_window: str | None = None
    confidence: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

class ScreenUnderstandingProvider(Protocol):
    async def observe_screen(self) -> ScreenObservation: ...
