"""Event-driven wakeups for missions; events are runtime data, never commands."""
from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

class EventType(str, Enum):
    USER_MESSAGE="user_message"; SCREEN_CHANGED="screen_changed"; WINDOW_CHANGED="window_changed"; BROWSER_NAVIGATED="browser_navigated"
    FILE_CREATED="file_created"; FILE_MODIFIED="file_modified"; FILE_DELETED="file_deleted"; PROCESS_STOPPED="process_stopped"
    TASK_COMPLETED="task_completed"; TASK_FAILED="task_failed"; AGENT_FAILED="agent_failed"; DEADLINE_APPROACHING="deadline_approaching"
    RESOURCE_AVAILABLE="resource_available"; RESOURCE_CONFLICT="resource_conflict"; APPROVAL_RECEIVED="approval_received"
    TIME_TRIGGERED="time_triggered"; MISSION_TRIGGERED="mission_triggered"; USER_TAKEOVER="user_takeover"

@dataclass(frozen=True, slots=True)
class AutonomousEvent:
    type: EventType
    mission_id: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

class AutonomousEventBus:
    def __init__(self) -> None: self._queue: asyncio.Queue[AutonomousEvent] = asyncio.Queue(); self.history: list[AutonomousEvent] = []
    async def publish(self, event: AutonomousEvent) -> None: self.history.append(event); await self._queue.put(event)
    async def next(self, timeout: float | None = None) -> AutonomousEvent | None:
        try:
            if timeout == 0:
                return self._queue.get_nowait()
            return await asyncio.wait_for(self._queue.get(), timeout) if timeout is not None else await self._queue.get()
        except (TimeoutError, asyncio.QueueEmpty): return None
