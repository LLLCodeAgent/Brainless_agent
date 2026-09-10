"""Run the authenticated Brainless Agent web command center."""
from __future__ import annotations
import asyncio
import os
from pathlib import Path
from app.bootstrap import Application
from app.config.settings import load_settings
from app.dashboard import DashboardRuntime, DashboardServer, DashboardService, RuntimeCommandGateway
from app.autonomy.events import AutonomousEventBus
from app.autonomy.event_store import EventStore
from app.autonomy.mission import MissionStore
from app.autonomy.operator import AutonomousOperator
from app.autonomy.perception_service import PerceptionService

async def _unconfigured_runner(_):
    raise RuntimeError("Mission execution runner is not configured for dashboard-only startup")

def main() -> None:
    token=os.environ.get("BRAINLESS_DASHBOARD_TOKEN","")
    if len(token)<16: raise SystemExit("Set BRAINLESS_DASHBOARD_TOKEN to at least 16 characters")
    root=Path(__file__).resolve().parent; app=Application(root,load_settings()); event_store=EventStore(root/"data/dashboard-events.db"); events=AutonomousEventBus(persistence=event_store); missions=MissionStore(root/"data/missions.json")
    operator=AutonomousOperator(missions,PerceptionService(app.autonomous_actions.controller,app.autonomous_actions.world_state,events),events,_unconfigured_runner)
    runtime=DashboardRuntime(missions,events,operator,app.agent_manager,app.autonomous_actions,
        provider_names=app.providers.names, mission_execution_status="not_configured")
    gateway=RuntimeCommandGateway(runtime,token); server=DashboardServer(DashboardService(runtime),gateway,port=8765)
    server.start(); print("Command Center: http://127.0.0.1:8765")
    try:
        import time
        while True: time.sleep(1)
    except KeyboardInterrupt: pass
    finally: server.close(); event_store.close(); asyncio.run(app.close())
if __name__=="__main__": main()
