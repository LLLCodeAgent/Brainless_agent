"""Goal-based task engine with durable journal checkpoints and final verification."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol
from uuid import uuid4

from app.autonomy.executor import ActionRuntime, DecisionProvider
from app.autonomy.orchestrator import AutonomousRuntime


class TaskOutcome(str, Enum):
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class AutonomousTask:
    objective: str
    acceptance_criteria: tuple["GoalCriterion", ...]
    task_id: str = field(default_factory=lambda: str(uuid4()))


class GoalCriterion(Protocol):
    async def verify(self, runtime: ActionRuntime) -> tuple[bool, str]: ...


@dataclass(frozen=True, slots=True)
class TaskResult:
    task_id: str
    outcome: TaskOutcome
    result: str
    verified: bool
    unmet_criteria: tuple[str, ...] = ()


class AutonomousTaskEngine:
    """Coordinates reusable agents, closed-loop action runtime, checkpoints, and goal verification."""
    def __init__(self, runtime: AutonomousRuntime, actions: ActionRuntime, journal=None) -> None:
        self.runtime, self.actions, self.journal = runtime, actions, journal

    async def run(self, root_agent_id: str, task: AutonomousTask, decider: DecisionProvider) -> TaskResult:
        self._journal(task.task_id, "TASK_CREATED", {"objective": task.objective})
        self._journal(task.task_id, "TASK_PLANNED", {"criteria": len(task.acceptance_criteria)})
        try:
            execution = await self.runtime.execute(root_agent_id, task.task_id, task.objective, decider)
        except Exception as error:
            self._journal(task.task_id, "TASK_FAILED", {"error": str(error)})
            return TaskResult(task.task_id, TaskOutcome.FAILED, str(error), False)
        self._journal(task.task_id, "CHECKPOINT_CREATED", {"agent_id": execution.agent_id, "result": execution.result})
        unmet_list: list[str] = []
        for criterion in task.acceptance_criteria:
            passed, detail = await criterion.verify(self.actions)
            if not passed:
                unmet_list.append(detail)
        unmet = tuple(unmet_list)
        if not unmet:
            self._journal(task.task_id, "TASK_COMPLETED", {"agent_id": execution.agent_id})
            return TaskResult(task.task_id, TaskOutcome.COMPLETED, execution.result, True)
        self._journal(task.task_id, "TASK_PARTIALLY_COMPLETED", {"unmet": list(unmet)})
        return TaskResult(task.task_id, TaskOutcome.PARTIALLY_COMPLETED, execution.result, False, unmet)

    def _journal(self, task_id: str, event: str, detail: dict[str, object]) -> None:
        if self.journal:
            self.journal.store_task_journal(task_id, event, detail)
