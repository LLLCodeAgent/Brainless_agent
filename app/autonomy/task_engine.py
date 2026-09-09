"""Goal engine that executes validated task graphs and verifies acceptance criteria."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol
from uuid import uuid4

from app.autonomy.checkpoints import CheckpointStore, ExecutionCheckpoint
from app.autonomy.executor import ActionRuntime, DecisionProvider
from app.autonomy.orchestrator import AutonomousRuntime
from app.autonomy.task_graph import GraphTask, GraphTaskStatus, TaskGraph, TaskScheduler


class TaskOutcome(str, Enum):
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class AutonomousTask:
    objective: str
    acceptance_criteria: tuple["GoalCriterion", ...]
    task_id: str = field(default_factory=lambda: str(uuid4()))


class GoalCriterion(Protocol):
    async def verify(self, runtime: ActionRuntime) -> tuple[bool, str]: ...


class GoalCompletionVerifier:
    async def verify(self, criteria: tuple[GoalCriterion, ...], runtime: ActionRuntime) -> tuple[bool, tuple[str, ...]]:
        unmet: list[str] = []
        for criterion in criteria:
            passed, detail = await criterion.verify(runtime)
            if not passed:
                unmet.append(detail)
        return not unmet, tuple(unmet)


@dataclass(frozen=True, slots=True)
class TaskResult:
    task_id: str
    outcome: TaskOutcome
    result: str
    verified: bool
    unmet_criteria: tuple[str, ...] = ()
    completed_tasks: tuple[str, ...] = ()
    blocked_reason: str | None = None


class AutonomousTaskEngine:
    """Coordinates agents, graph scheduling, final verification, and append-only journaling."""
    def __init__(self, runtime: AutonomousRuntime, actions: ActionRuntime, journal=None,
                 scheduler: TaskScheduler | None = None, verifier: GoalCompletionVerifier | None = None,
                 checkpoints: CheckpointStore | None = None) -> None:
        self.runtime, self.actions, self.journal, self.checkpoints = runtime, actions, journal, checkpoints
        self.scheduler, self.verifier = scheduler or TaskScheduler(), verifier or GoalCompletionVerifier()

    async def run(self, root_agent_id: str, task: AutonomousTask, decider: DecisionProvider) -> TaskResult:
        """Backward-compatible single-node goal execution and journal vocabulary."""
        self._journal(task.task_id, "TASK_CREATED", {"objective": task.objective})
        self._journal(task.task_id, "TASK_PLANNED", {"criteria": len(task.acceptance_criteria)})
        try:
            execution = await self.runtime.execute(root_agent_id, task.task_id, task.objective, decider)
        except Exception as error:
            self._journal(task.task_id, "TASK_FAILED", {"error": str(error)})
            return TaskResult(task.task_id, TaskOutcome.FAILED, str(error), False)
        self._journal(task.task_id, "CHECKPOINT_CREATED", {"agent_id": execution.agent_id, "result": execution.result})
        succeeded, unmet = await self.verifier.verify(task.acceptance_criteria, self.actions)
        if succeeded:
            self._journal(task.task_id, "TASK_COMPLETED", {"agent_id": execution.agent_id})
            return TaskResult(task.task_id, TaskOutcome.COMPLETED, execution.result, True)
        self._journal(task.task_id, "TASK_PARTIALLY_COMPLETED", {"unmet": list(unmet)})
        return TaskResult(task.task_id, TaskOutcome.PARTIALLY_COMPLETED, execution.result, False, unmet)

    async def run_graph(self, root_agent_id: str, task: AutonomousTask, graph: TaskGraph,
                        decider_for: Callable[[GraphTask], DecisionProvider], *, dry_run: bool = False) -> TaskResult:
        graph.validate()
        self._journal(task.task_id, "GOAL_CREATED", {"objective": task.objective})
        self._journal(task.task_id, "PLAN_CREATED", {"tasks": sorted(graph.tasks)})
        self._checkpoint(task, graph)
        if dry_run:
            return TaskResult(task.task_id, TaskOutcome.BLOCKED, "Dry run: no actions executed", False,
                              tuple(), tuple(), "dry_run")
        completed: list[str] = []
        while ready := self.scheduler.next_tasks(graph, set(self.actions.locks.owners), limit=1):
            node = ready[0]
            node.status = GraphTaskStatus.RUNNING
            self._journal(task.task_id, "TASK_CREATED", {"node": node.task_id, "objective": node.objective})
            try:
                execution = await self.runtime.execute(root_agent_id, f"{task.task_id}:{node.task_id}", node.objective,
                                                       decider_for(node))
            except Exception as error:
                graph.fail(node.task_id, str(error))
                self._checkpoint(task, graph)
                self._journal(task.task_id, "TASK_FAILED", {"node": node.task_id, "error": str(error)})
                continue
            graph.complete(node.task_id)
            completed.append(node.task_id)
            self._checkpoint(task, graph)
            self._journal(task.task_id, "TASK_COMPLETED", {"node": node.task_id, "agent_id": execution.agent_id})
        succeeded, unmet = await self.verifier.verify(task.acceptance_criteria, self.actions)
        if succeeded and all(node.status is GraphTaskStatus.COMPLETED for node in graph.tasks.values()):
            self._journal(task.task_id, "GOAL_COMPLETED", {"completed": completed})
            return TaskResult(task.task_id, TaskOutcome.COMPLETED, "Goal acceptance criteria verified", True,
                              completed_tasks=tuple(completed))
        blocked = tuple(node for node in graph.tasks.values() if node.status is GraphTaskStatus.BLOCKED)
        failed = tuple(node for node in graph.tasks.values() if node.status is GraphTaskStatus.FAILED)
        outcome = TaskOutcome.BLOCKED if blocked else TaskOutcome.PARTIALLY_COMPLETED if completed else TaskOutcome.FAILED
        reason = (blocked[0].error if blocked else failed[0].error if failed else "Acceptance criteria were not met")
        self._journal(task.task_id, "GOAL_VERIFICATION_FAILED", {"unmet": list(unmet), "reason": reason})
        return TaskResult(task.task_id, outcome, "Goal was not fully verified", False, unmet, tuple(completed), reason)

    def _checkpoint(self, task: AutonomousTask, graph: TaskGraph) -> None:
        if not self.checkpoints:
            return
        graph_data = {task_id: {"status": node.status.value, "dependencies": sorted(node.dependencies),
                                "retries": node.retries, "error": node.error} for task_id, node in graph.tasks.items()}
        agents = {agent.agent_id: agent.status.value for agent in self.runtime.manager.list_agents()}
        world = self.actions.world_state.snapshot().values()
        self.checkpoints.save(ExecutionCheckpoint(task.objective, graph_data, world, agents,
            tuple(task_id for task_id, node in graph.tasks.items() if node.status is GraphTaskStatus.PENDING),
            {task_id: node.retries for task_id, node in graph.tasks.items()},
            {agent.agent_id: tuple(sorted(agent.permissions)) for agent in self.runtime.manager.list_agents()},
            self.actions.locks.owners))

    def _journal(self, task_id: str, event: str, detail: dict[str, object]) -> None:
        if self.journal:
            self.journal.store_task_journal(task_id, event, detail)
