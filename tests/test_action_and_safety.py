import pytest

from app.runtime.action_manager import ActionLimitExceeded, ActionManager
from app.safety.emergency_stop import EmergencyStop, EmergencyStopRequested


def test_action_manager_enforces_limit() -> None:
    actions = ActionManager(1)
    actions.record("first")
    with pytest.raises(ActionLimitExceeded):
        actions.record("second")


def test_emergency_stop_latch_can_be_triggered_and_cleared() -> None:
    stop = EmergencyStop()
    stop.trigger()
    with pytest.raises(EmergencyStopRequested):
        stop.raise_if_triggered()
    stop.clear()
    stop.raise_if_triggered()
