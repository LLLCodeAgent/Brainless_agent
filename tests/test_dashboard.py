import asyncio
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from app.agents.manager import AgentManager
from app.autonomy.controllers import FilesystemComputerController
from app.autonomy.events import AutonomousEvent, AutonomousEventBus, EventType
from app.autonomy.executor import ActionRuntime
from app.autonomy.mission import Mission, MissionStatus, MissionStore
from app.autonomy.operator import AutonomousOperator
from app.autonomy.perception_service import PerceptionService
from app.dashboard import DashboardRuntime, DashboardServer, DashboardService, RuntimeCommandGateway

TOKEN = "test-dashboard-token-123"


def dashboard(tmp_path):
    manager = AgentManager()
    manager.create_root("Operator", "root", "supervise", set())
    controller = FilesystemComputerController(tmp_path)
    actions = ActionRuntime(manager, controller)
    events = AutonomousEventBus()
    store = MissionStore(tmp_path / "missions.json")
    async def runner(_): return MissionStatus.COMPLETED
    operator = AutonomousOperator(store, PerceptionService(controller, actions.world_state, events), events, runner)
    runtime = DashboardRuntime(store, events, operator, manager, actions)
    return runtime, DashboardService(runtime), RuntimeCommandGateway(runtime, TOKEN)


def test_dashboard_snapshot_uses_real_runtime_state_and_redacts_secrets(tmp_path):
    runtime, service, _ = dashboard(tmp_path)
    mission = Mission("real mission", "user", task_graph={"task": {"objective": "work", "status": "running"}},
                      current_state={"api_token": "never-show"})
    runtime.missions.save(mission)
    snapshot = service.snapshot()
    assert snapshot["overview"]["active_missions"] == 1
    assert snapshot["overview"]["active_tasks"] == 1
    assert snapshot["overview"]["active_agents"] == 0
    assert snapshot["missions"][0]["current_state"]["api_token"] == "[REDACTED]"


def test_dashboard_commands_require_authorization_and_emit_correlated_event(tmp_path):
    runtime, _, gateway = dashboard(tmp_path)
    mission = Mission("pause me", "user"); runtime.missions.save(mission)
    with pytest.raises(PermissionError):
        asyncio.run(gateway.execute("wrong-token-value", "pause_mission", {"mission_id": mission.mission_id}))
    result = asyncio.run(gateway.execute(TOKEN, "pause_mission", {"mission_id": mission.mission_id}))
    assert runtime.missions.load(mission.mission_id).status is MissionStatus.PAUSED
    event = runtime.events.replay()[0]
    assert result["correlation_id"] == event.correlation_id


def test_dashboard_http_api_auth_static_load_and_replay(tmp_path):
    runtime, service, gateway = dashboard(tmp_path)
    asyncio.run(runtime.events.publish(AutonomousEvent(EventType.MISSION_TRIGGERED, "mission")))
    server = DashboardServer(service, gateway); server.start()
    host, port = server.address; base = f"http://{host}:{port}"
    try:
        assert b"Command Center" in urlopen(base + "/", timeout=2).read()
        with pytest.raises(HTTPError) as denied:
            urlopen(base + "/api/system", timeout=2)
        assert denied.value.code == 401
        request = Request(base + "/api/system", headers={"Authorization": f"Bearer {TOKEN}"})
        payload = json.loads(urlopen(request, timeout=2).read())
        assert payload["events"][0]["mission_id"] == "mission"
        request = Request(base + "/api/events?since=1", headers={"Authorization": f"Bearer {TOKEN}"})
        assert json.loads(urlopen(request, timeout=2).read()) == []
    finally:
        server.close()


def test_dashboard_event_history_survives_gateway_restart(tmp_path):
    from app.autonomy.event_store import EventStore
    path = tmp_path / "events.db"
    store = EventStore(path); first = AutonomousEventBus(persistence=store)
    asyncio.run(first.publish(AutonomousEvent(EventType.TASK_COMPLETED, "mission", {"status": "completed"})))
    store.close()
    reopened = EventStore(path); restored = AutonomousEventBus(persistence=reopened)
    try:
        assert restored.replay()[0].mission_id == "mission"
        assert restored.replay()[0].sequence == 1
    finally:
        reopened.close()


def test_authorized_create_mission_uses_operator_and_validates_input(tmp_path):
    runtime, _, gateway = dashboard(tmp_path)
    result = asyncio.run(gateway.execute(TOKEN, "create_mission", {"goal": "Monitor project", "priority": 4}))
    mission = runtime.missions.load(runtime.events.replay()[-1].mission_id)
    assert result["accepted"] and mission.goal == "Monitor project" and mission.priority == 4
    with pytest.raises(ValueError):
        asyncio.run(gateway.execute(TOKEN, "create_mission", {"goal": ""}))
