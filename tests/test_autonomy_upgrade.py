import asyncio
from datetime import datetime, timedelta, timezone

from app.agents.manager import AgentManager
from app.autonomy.contracts import ActionContract, Idempotency, RetryPolicy
from app.autonomy.executor import ActionRuntime
from app.autonomy.orchestrator import AutonomousRuntime
from app.autonomy.models import ComputerAction, ComputerState
from app.autonomy.recovery import RecoveryEngine, RecoveryStrategy
from app.autonomy.task_graph import GraphTask, GraphTaskStatus, TaskGraph, TaskScheduler
from app.autonomy.world_state import FactKind, WorldStateManager
from app.safety.permissions import Permission


class MovingUi:
    def __init__(self): self.submitted = False
    async def observe(self):
        return ComputerState(active_application="browser", browser_url="https://test/success" if self.submitted else "https://test/form",
            visible_ui=("Submission confirmed" if self.submitted else "Submit button",))
    async def execute(self, action, arguments): self.submitted = True; return "click accepted"


def test_world_state_marks_old_facts_stale_and_diffs_observations():
    world = WorldStateManager(timedelta(seconds=1))
    old = ComputerState(timestamp=datetime.now(timezone.utc) - timedelta(seconds=5), browser_url="https://old")
    before = world.capture(old, evidence="screen-1")
    assert world.get("browser_url").kind is FactKind.STALE
    after = world.capture(ComputerState(browser_url="https://new"), evidence="screen-2")
    assert world.diff(before, after)["browser_url"] == ("https://old", "https://new")
    assert world.get("browser_url", require_observed=True).evidence == "screen-2"


def test_action_contract_requires_observed_precondition_then_verifies_real_ui_transition():
    async def scenario():
        manager = AgentManager()
        root = manager.create_root("root", "root", "submit", {Permission.SCREEN_READ.value, Permission.MOUSE_CLICK.value})
        ui = MovingUi()
        contract = ActionContract("submit", "mouse.click", frozenset({Permission.MOUSE_CLICK.value}),
            preconditions={"browser_url": "https://test/form"}, expected_effects={"browser_url": "https://test/success"},
            retry=RetryPolicy(2), idempotency=Idempotency.NOT_SAFE_TO_RETRY, risk="high")
        runtime = ActionRuntime(manager, ui, contracts={"mouse.click": contract})
        child = manager.create_agent(root.agent_id, "computer", "computer", "submit", permissions={Permission.SCREEN_READ.value, Permission.MOUSE_CLICK.value}, tools={"mouse.click"})
        async def work(agent, _):
            result = await runtime.perform(ComputerAction("mouse.click", {"x": 1, "y": 1}, agent.agent_id, "submit", "click", Permission.MOUSE_CLICK.value))
            assert result.success and result.verified
            return "verified"
        assert await manager.start_agent(root.agent_id, child.agent_id, work) == "verified"
        assert runtime.world_state.get("browser_url", require_observed=True).value.endswith("success")
    asyncio.run(scenario())


def test_task_graph_scheduler_dependencies_conflicts_and_replanning():
    graph = TaskGraph(); graph.add(GraphTask("research", "research", resources=frozenset({"browser"}), priority=1)); graph.add(GraphTask("write", "write", {"research"}, resources=frozenset({"filesystem"}), priority=10)); graph.add(GraphTask("review", "review", resources=frozenset({"browser"}), priority=3))
    scheduler = TaskScheduler()
    assert [t.task_id for t in scheduler.next_tasks(graph, set(), 2)] == ["review"]
    graph.complete("research")
    assert [t.task_id for t in scheduler.next_tasks(graph, set(), 2)] == ["write", "review"]
    graph.fail("write", "transient"); assert graph.tasks["write"].status is GraphTaskStatus.PENDING
    graph.replan(remove=["review"]); assert "review" not in graph.tasks


def test_recovery_never_blindly_retries_non_idempotent_unverified_action():
    engine = RecoveryEngine()
    assert engine.choose("VERIFICATION_FAILED: missing receipt", Idempotency.NOT_SAFE_TO_RETRY, 0, 2) is RecoveryStrategy.REOBSERVE
    assert engine.choose("PERMISSION_DENIED: blocked", Idempotency.SAFE_TO_RETRY, 0, 2) is RecoveryStrategy.HUMAN_APPROVAL


def test_target_resolution_and_atomic_checkpoint_roundtrip(tmp_path):
    from app.autonomy.checkpoints import CheckpointStore, ExecutionCheckpoint
    from app.autonomy.target import TargetResolver
    target = TargetResolver().resolve("submit", ComputerState(visible_ui=("Submit button",)))
    assert target and target.method == "text" and target.confidence >= .75
    store = CheckpointStore(tmp_path / "checkpoints" / "goal.json")
    checkpoint = ExecutionCheckpoint("save report", {"write": "completed"}, {"file": "report.pdf"}, {"agent": "ready"}, ("verify",), {"write": 1})
    store.save(checkpoint)
    assert store.load() == checkpoint


def test_graph_goal_executes_dependencies_and_verifies_real_filesystem_result(tmp_path):
    from app.autonomy.controllers import FilesystemComputerController
    from app.autonomy.task_engine import AutonomousTask, AutonomousTaskEngine, TaskOutcome

    class Criterion:
        async def verify(self, _):
            report = tmp_path / "report.txt"
            return (report.is_file() and "comparison" in report.read_text(), "verified report missing")

    class Write:
        def __init__(self, path, content): self.path, self.content, self.done = path, content, False
        async def next_action(self, _):
            if self.done: return None
            self.done = True
            from app.autonomy.models import ActionProposal
            return ActionProposal("filesystem.write", {"path": self.path, "content": self.content}, "persist result")

    async def scenario():
        manager = AgentManager()
        root = manager.create_root("root", "root", "report", {Permission.SCREEN_READ.value, Permission.FILESYSTEM_WRITE.value})
        actions = ActionRuntime(manager, FilesystemComputerController(tmp_path))
        graph = TaskGraph(); graph.add(GraphTask("research", "save source")); graph.add(GraphTask("report", "save comparison", {"research"}))
        decisions = {"research": Write("source.txt", "research"), "report": Write("report.txt", "comparison\nresearch")}
        result = await AutonomousTaskEngine(AutonomousRuntime(manager, actions), actions).run_graph(root.agent_id, AutonomousTask("create report", (Criterion(),)), graph, lambda node: decisions[node.task_id])
        assert result.outcome is TaskOutcome.COMPLETED and result.completed_tasks == ("research", "report")
        assert (tmp_path / "source.txt").is_file() and (tmp_path / "report.txt").is_file()
    asyncio.run(scenario())


def test_action_audit_redacts_secret_values(tmp_path):
    async def scenario():
        manager = AgentManager()
        root = manager.create_root("root", "root", "write", {Permission.SCREEN_READ.value, Permission.KEYBOARD_WRITE.value})
        runtime = ActionRuntime(manager, MovingUi())
        child = manager.create_agent(root.agent_id, "writer", "writer", "write", permissions={Permission.SCREEN_READ.value, Permission.KEYBOARD_WRITE.value}, tools={"keyboard.write"})
        async def work(agent, _):
            await runtime.perform(ComputerAction("keyboard.write", {"text": "hello", "password": "do-not-log"}, agent.agent_id, "task", "write", Permission.KEYBOARD_WRITE.value))
            return "done"
        await manager.start_agent(root.agent_id, child.agent_id, work)
        assert runtime.audit[-1].arguments["password"] == "[REDACTED]"
    asyncio.run(scenario())


def test_graph_checkpoint_is_updated_and_resume_forces_new_observation(tmp_path):
    from app.autonomy.checkpoints import CheckpointStore
    from app.autonomy.controllers import FilesystemComputerController
    from app.autonomy.task_engine import AutonomousTask, AutonomousTaskEngine, TaskOutcome
    from app.autonomy.models import ActionProposal

    class Criterion:
        async def verify(self, _): return ((tmp_path / "done.txt").is_file(), "file missing")
    class Decision:
        def __init__(self): self.done = False
        async def next_action(self, _):
            if self.done: return None
            self.done = True
            return ActionProposal("filesystem.write", {"path": "done.txt", "content": "done"}, "write")

    async def scenario():
        manager = AgentManager()
        root = manager.create_root("root", "root", "goal", {Permission.SCREEN_READ.value, Permission.FILESYSTEM_WRITE.value})
        controller = FilesystemComputerController(tmp_path)
        actions = ActionRuntime(manager, controller)
        store = CheckpointStore(tmp_path / "checkpoint.json")
        engine = AutonomousTaskEngine(AutonomousRuntime(manager, actions), actions, checkpoints=store)
        graph = TaskGraph(); graph.add(GraphTask("write", "create a file"))
        result = await engine.run_graph(root.agent_id, AutonomousTask("save", (Criterion(),)), graph, lambda _: Decision())
        assert result.outcome is TaskOutcome.COMPLETED
        checkpoint = store.load()
        assert checkpoint and checkpoint.task_graph["write"]["status"] == "completed"
        resumed = await store.resume(controller.observe)
        assert resumed and resumed[0].pending_actions == () and resumed[1].active_application == "filesystem"
    asyncio.run(scenario())
