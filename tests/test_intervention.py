import asyncio

import pytest

from app.safety.emergency_stop import EmergencyStop, EmergencyStopRequested
from app.safety.intervention import UserInterventionGate


def test_intervention_gate_waits_for_explicit_continue() -> None:
    async def scenario() -> None:
        notifications: list[str] = []
        gate = UserInterventionGate(notifications.append)
        waiting = asyncio.create_task(gate.wait("Sign in", EmergencyStop()))
        await asyncio.sleep(0)
        assert not waiting.done()
        assert notifications == ["Sign in"]
        gate.continue_run()
        await waiting
    asyncio.run(scenario())


def test_intervention_gate_obeys_emergency_stop() -> None:
    async def scenario() -> None:
        stop = EmergencyStop()
        gate = UserInterventionGate()
        waiting = asyncio.create_task(gate.wait("Sign in", stop))
        await asyncio.sleep(0)
        stop.trigger()
        with pytest.raises(EmergencyStopRequested):
            await waiting
    asyncio.run(scenario())
