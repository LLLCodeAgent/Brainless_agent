"""Async resource locks prevent conflicting control of a shared computer."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator


class ResourceLockManager:
    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}
        self._owners: dict[str, str] = {}

    @asynccontextmanager
    async def acquire(self, agent_id: str, resources: set[str]) -> AsyncIterator[None]:
        ordered = sorted(resources)
        locks = [self._locks.setdefault(resource, asyncio.Lock()) for resource in ordered]
        for lock in locks:
            await lock.acquire()
        self._owners.update({resource: agent_id for resource in ordered})
        try:
            yield
        finally:
            for resource in reversed(ordered):
                self._owners.pop(resource, None)
                self._locks[resource].release()

    @property
    def owners(self) -> dict[str, str]:
        return dict(self._owners)
