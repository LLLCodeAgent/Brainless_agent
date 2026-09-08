import asyncio

from app.runtime.recovery_manager import RecoveryManager
from app.runtime.state_manager import RuntimeState, StateManager


def test_state_transitions_are_recorded() -> None:
    manager = StateManager()
    manager.transition(RuntimeState.INITIALIZING)
    manager.transition(RuntimeState.COMPLETED)
    assert manager.history == [RuntimeState.IDLE, RuntimeState.INITIALIZING, RuntimeState.COMPLETED]


def test_recovery_retries_after_failure() -> None:
    attempts = 0
    recoveries = 0

    async def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("temporary")
        return "ok"

    async def recover() -> None:
        nonlocal recoveries
        recoveries += 1

    assert asyncio.run(RecoveryManager(1).run(operation, recover)) == "ok"
    assert recoveries == 1
