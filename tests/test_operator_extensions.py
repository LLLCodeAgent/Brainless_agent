import asyncio
from datetime import datetime, timedelta, timezone

from app.autonomy.events import AutonomousEvent, AutonomousEventBus, EventType
from app.autonomy.triggers import FilesystemWatcher, Trigger, TriggerEngine, TriggerKind, TriggerStore


def test_persisted_time_and_filesystem_triggers_are_deterministic(tmp_path):
    async def scenario():
        events = AutonomousEventBus(); store = TriggerStore(tmp_path / "triggers.json")
        trigger = Trigger("mission", TriggerKind.TIME, (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat())
        store.save(trigger)
        assert (await TriggerEngine(store, events).tick())[0].trigger_id == trigger.trigger_id
        assert (await events.next(0)).type is EventType.TIME_TRIGGERED
    asyncio.run(scenario())
    watcher = FilesystemWatcher(tmp_path); assert watcher.poll() == ()
    (tmp_path / "new.txt").write_text("new")
    assert EventType.FILE_CREATED in watcher.poll()


def test_health_monitor_releases_dead_agent_resources_without_escalation():
    from app.agents.manager import AgentManager
    from app.agents.models import AgentStatus
    from app.autonomy.health import AgentHealthMonitor
    from app.autonomy.resources import ResourceLockManager
    async def scenario():
        manager = AgentManager(); root = manager.create_root("root", "root", "goal", set())
        child = manager.create_agent(root.agent_id, "worker", "worker", "work", task="task")
        locks = ResourceLockManager()
        async with locks.acquire(child.agent_id, {"browser"}):
            child.status = AgentStatus.FAILED
            health = AgentHealthMonitor(manager, locks).inspect()
            assert not health[1].healthy and health[1].released_resources == ("browser",)
    asyncio.run(scenario())


def test_mode_policy_blocks_watch_and_requires_supervised_approval():
    from app.agents.tools import RiskLevel, ToolSpec
    from app.autonomy.mode_policy import ModePolicy
    from app.autonomy.operator import AutonomyMode
    high = ToolSpec("danger", "danger", "", frozenset(), RiskLevel.HIGH, lambda _: None)
    assert ModePolicy(AutonomyMode.WATCH).decision(high) == "deny"
    assert ModePolicy(AutonomyMode.SUPERVISED).decision(high) == "approval"


def test_task_engine_mission_runner_restores_graph_and_maps_verified_outcome():
    from app.autonomy.mission import Mission, MissionStatus
    from app.autonomy.task_engine import TaskResult, TaskOutcome
    from app.autonomy.task_graph import GraphTask, TaskGraph
    from app.autonomy.task_runner import TaskEngineMissionRunner

    class Engine:
        async def run_graph(self, root, task, graph, decider):
            assert root == "root" and graph.tasks["first"].status.value == "completed"
            graph.complete("second")
            return TaskResult(task.task_id, TaskOutcome.COMPLETED, "done", True, completed_tasks=("first", "second"))
    def graph_for(_):
        graph = TaskGraph(); graph.add(GraphTask("first", "first")); graph.add(GraphTask("second", "second", {"first"})); return graph
    runner = TaskEngineMissionRunner(Engine(), "root", graph_for, lambda _: None, lambda _: ())
    mission = Mission("goal", "user", checkpoint={"task_graph": {"first": {"status": "completed"}}})
    assert asyncio.run(runner(mission)) is MissionStatus.COMPLETED
    assert mission.checkpoint["verified"] and mission.task_graph["second"]["status"] == "completed"


def test_condition_and_prerequisite_mission_triggers_respect_runtime_policy(tmp_path):
    async def scenario():
        events = AutonomousEventBus(); store = TriggerStore(tmp_path / "triggers.json")
        condition = {"ready": False}
        blocked = Trigger("blocked", TriggerKind.CONDITION, "ready")
        prerequisite = Trigger("dependent", TriggerKind.MISSION, "source")
        store.save(blocked); store.save(prerequisite)
        engine = TriggerEngine(store, events, conditions={"ready": lambda: condition["ready"]})
        assert await engine.tick() == ()
        condition["ready"] = True
        assert (await engine.tick())[0].mission_id == "blocked"
        assert (await engine.handle(AutonomousEvent(EventType.TASK_COMPLETED, "source")))[0].mission_id == "dependent"
    asyncio.run(scenario())


def test_benchmark_harness_records_verified_local_report_workflow(tmp_path):
    from app.autonomy.benchmark import BenchmarkHarness
    async def report_scenario():
        source = tmp_path / "source.txt"; source.write_text("research")
        report = tmp_path / "report.pdf"; report.write_bytes(b"%PDF-1.4\nresearch")
        archive = tmp_path / "archive"; archive.mkdir(); source.replace(archive / source.name)
        verified = report.read_bytes().startswith(b"%PDF") and (archive / "source.txt").is_file()
        return verified, verified, {"steps": 3, "agents": 1}
    result = asyncio.run(BenchmarkHarness().run("report_pdf_organize", report_scenario))
    assert result.success and result.verified and result.steps == 3


def test_interruption_and_presence_detection_keep_user_data_out_of_runtime():
    from app.autonomy.monitoring import InterruptionKind, InterruptionManager, UserPresenceDetector
    from app.autonomy.models import ComputerState
    interruption = InterruptionManager().classify(ComputerState(visible_ui=("Please sign in",)))
    assert interruption.kind is InterruptionKind.LOGIN and interruption.requires_user
    detector = UserPresenceDetector(lambda: True)
    assert detector.present() and detector.last_seen is not None


def test_supervised_runtime_waits_for_independent_approval_before_execution(tmp_path):
    from app.agents.manager import AgentManager
    from app.autonomy.approvals import ApprovalStatus, ApprovalStore, ApprovalSystem
    from app.autonomy.controllers import FilesystemComputerController
    from app.autonomy.executor import ActionRuntime
    from app.autonomy.mode_policy import ModePolicy
    from app.autonomy.models import ActionProposal
    from app.autonomy.operator import AutonomyMode
    from app.safety.permissions import Permission

    async def scenario():
        manager = AgentManager()
        root = manager.create_root("root", "root", "goal", {Permission.FILESYSTEM_WRITE.value})
        approvals = ApprovalSystem(ApprovalStore(tmp_path / "approvals.json"), manager, timeout_seconds=2)
        runtime = ActionRuntime(manager, FilesystemComputerController(tmp_path),
            approval_handler=approvals.request, mode_policy=ModePolicy(AutonomyMode.SUPERVISED))
        child = manager.create_agent(root.agent_id, "writer", "writer", "write", task="write",
            permissions={Permission.FILESYSTEM_WRITE.value}, tools={"filesystem.write"}, task_id="task")
        async def work(agent, _):
            pending = asyncio.create_task(runtime.perform_proposal(agent.agent_id, "task",
                ActionProposal("filesystem.write", {"path": "approved.txt", "content": "yes"}, "write approved file")))
            await asyncio.sleep(.05)
            request = approvals.store.all()[0]
            assert not (tmp_path / "approved.txt").exists()
            approvals.decide(request.approval_id, ApprovalStatus.APPROVED, "human")
            result = await pending
            assert result.success and (tmp_path / "approved.txt").read_text() == "yes"
            return "done"
        await manager.start_agent(root.agent_id, child.agent_id, work)
    asyncio.run(scenario())
