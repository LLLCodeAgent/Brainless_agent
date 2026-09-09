"""Async resource ownership with ordered acquisition and forced failure cleanup."""
from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator


class ResourceBusyError(TimeoutError): pass


class ResourceLockManager:
    """Ordered locks prevent deadlocks; ownership is inspectable for supervision."""
    def __init__(self, default_timeout: float | None = 30.0) -> None:
        self.default_timeout = default_timeout
        self._locks: dict[str, asyncio.Lock] = {}
        self._owners: dict[str, str] = {}

    @asynccontextmanager
    async def acquire(self, agent_id: str, resources: set[str], timeout: float | None = None) -> AsyncIterator[None]:
        ordered = sorted(resources); acquired: list[str] = []
        try:
            for resource in ordered:
                lock = self._locks.setdefault(resource, asyncio.Lock())
                try:
                    await asyncio.wait_for(lock.acquire(), self.default_timeout if timeout is None else timeout)
                except TimeoutError as error:
                    raise ResourceBusyError(f"Timed out waiting for resource {resource}") from error
                acquired.append(resource); self._owners[resource] = agent_id
            yield
        finally:
            for resource in reversed(acquired):
                if self._owners.get(resource) == agent_id: self._owners.pop(resource, None)
                if self._locks[resource].locked(): self._locks[resource].release()

    def release_agent(self, agent_id: str) -> tuple[str, ...]:
        """Best-effort cleanup for an agent that died outside its context manager."""
        released = [resource for resource, owner in self._owners.items() if owner == agent_id]
        for resource in released:
            self._owners.pop(resource, None)
            if self._locks[resource].locked(): self._locks[resource].release()
        return tuple(released)

    @property
    def owners(self) -> dict[str, str]: return dict(self._owners)
