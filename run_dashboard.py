"""Run the authenticated Brainless Agent web command center and mission operator."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

from app.autonomy.event_store import EventStore
from app.autonomy.events import AutonomousEventBus
from app.autonomy.mission import MissionStore
from app.autonomy.operator import AutonomousOperator
from app.autonomy.perception_service import PerceptionService
from app.autonomy.production_mission import RuntimeMissionComposer
from app.autonomy.reasoning_provider import ChatbotReasoningProvider
from app.bootstrap import Application
from app.config.settings import load_settings
from app.dashboard import DashboardRuntime, DashboardServer, DashboardService, RuntimeCommandGateway
from app.dashboard.runtime_bridge import RuntimeEventBridge
from app.safety.permissions import Permission


async def _pump(bridge: RuntimeEventBridge) -> None:
    while True:
        await bridge.pump_once()
        await asyncio.sleep(.25)


async def serve() -> None:
    token = os.environ.get("BRAINLESS_DASHBOARD_TOKEN", "")
    if len(token) < 16:
        raise SystemExit("Set BRAINLESS_DASHBOARD_TOKEN to at least 16 characters")
    root = Path(__file__).resolve().parent
    application = Application(root, load_settings())
    event_store = EventStore(root / "data/dashboard-events.db")
    events = AutonomousEventBus(persistence=event_store)
    missions = MissionStore(root / "data/missions.json")
    execution_status = "not_configured"
    if application.providers.names:
        provider = application.providers.get(application.providers.names[0])
        application.autonomous.reasoning_provider = ChatbotReasoningProvider(provider)
        root_agent = application.agent_manager.create_root(
            "Root Operator", "orchestrator", "Supervise autonomous missions",
            {permission.value for permission in Permission})
        runner = RuntimeMissionComposer(application.autonomous, application.task_engine, root_agent.agent_id)
        execution_status = "healthy"
    else:
        async def runner(_):
            raise RuntimeError("No reasoning provider is configured")
    operator = AutonomousOperator(missions, PerceptionService(
        application.autonomous_actions.controller, application.autonomous_actions.world_state, events), events, runner)
    runtime = DashboardRuntime(missions, events, operator, application.agent_manager,
        application.autonomous_actions, provider_names=application.providers.names,
        mission_execution_status=execution_status)
    gateway = RuntimeCommandGateway(runtime, token)
    server = DashboardServer(DashboardService(runtime), gateway, port=8765)
    bridge_task = asyncio.create_task(_pump(RuntimeEventBridge(
        application.agent_manager, application.autonomous_actions, events)))
    operator_task = asyncio.create_task(operator.run_background(stop=lambda: False))
    server.start()
    print("Command Center: http://127.0.0.1:8765")
    try:
        await asyncio.Event().wait()
    finally:
        operator_task.cancel(); bridge_task.cancel()
        await asyncio.gather(operator_task, bridge_task, return_exceptions=True)
        server.close(); event_store.close(); await application.close()


def main() -> None:
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
