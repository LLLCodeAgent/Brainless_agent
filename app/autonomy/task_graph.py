"""Mutable dependency graph and deterministic resource-aware scheduling primitives."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Iterable


class GraphTaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    PAUSED = "paused"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class GraphTask:
    task_id: str
    objective: str
    dependencies: set[str] = field(default_factory=set)
    capabilities: frozenset[str] = frozenset()
    permissions: frozenset[str] = frozenset()
    resources: frozenset[str] = frozenset()
    tool: str | None = None
    priority: int = 0
    deadline: datetime | None = None
    estimated_cost: float = 0.0
    high_risk: bool = False
    requires_approval: bool = False
    status: GraphTaskStatus = GraphTaskStatus.PENDING
    retries: int = 0
    max_retries: int = 1
    error: str | None = None


class TaskGraph:
    def __init__(self) -> None:
        self.tasks: dict[str, GraphTask] = {}

    def add(self, task: GraphTask) -> None:
        if task.task_id in self.tasks:
            raise ValueError(f"Duplicate task {task.task_id}")
        if task.task_id in task.dependencies:
            raise ValueError("Task cannot depend on itself")
        self.tasks[task.task_id] = task

    def validate(self) -> None:
        for task in self.tasks.values():
            missing = task.dependencies - self.tasks.keys()
            if missing:
                raise ValueError(f"Unknown dependencies: {sorted(missing)}")
        visiting: set[str] = set()
        visited: set[str] = set()
        def visit(task_id: str) -> None:
            if task_id in visiting:
                raise ValueError("Task graph contains a cycle")
            if task_id not in visited:
                visiting.add(task_id)
                for parent in self.tasks[task_id].dependencies:
                    visit(parent)
                visiting.remove(task_id)
                visited.add(task_id)
        for task_id in self.tasks:
            visit(task_id)

    def runnable(self) -> tuple[GraphTask, ...]:
        return tuple(task for task in self.tasks.values() if task.status is GraphTaskStatus.PENDING and all(
            self.tasks[parent].status is GraphTaskStatus.COMPLETED for parent in task.dependencies))

    def complete(self, task_id: str) -> None:
        self.tasks[task_id].status = GraphTaskStatus.COMPLETED

    def fail(self, task_id: str, error: str) -> None:
        task = self.tasks[task_id]
        task.error = error
        if task.retries < task.max_retries:
            task.retries += 1
            task.status = GraphTaskStatus.PENDING
        else:
            task.status = GraphTaskStatus.FAILED
            self._block_dependents(task_id, f"Dependency {task_id} failed")

    def _block_dependents(self, task_id: str, reason: str) -> None:
        for candidate in self.tasks.values():
            if task_id in candidate.dependencies and candidate.status is GraphTaskStatus.PENDING:
                candidate.status, candidate.error = GraphTaskStatus.BLOCKED, reason
                self._block_dependents(candidate.task_id, reason)

    def pause(self, task_id: str) -> None:
        if self.tasks[task_id].status is GraphTaskStatus.PENDING:
            self.tasks[task_id].status = GraphTaskStatus.PAUSED

    def resume(self, task_id: str) -> None:
        if self.tasks[task_id].status is GraphTaskStatus.PAUSED:
            self.tasks[task_id].status = GraphTaskStatus.PENDING

    def cancel(self, task_id: str) -> None:
        self.tasks[task_id].status = GraphTaskStatus.CANCELLED
        self._block_dependents(task_id, f"Dependency {task_id} cancelled")

    def replan(self, remove: Iterable[str] = (), add: Iterable[GraphTask] = ()) -> None:
        for task_id in remove:
            if any(task_id in task.dependencies for task in self.tasks.values() if task.task_id not in remove):
                raise ValueError("Cannot remove a task that remaining tasks depend on")
            self.tasks.pop(task_id, None)
        for task in add:
            self.add(task)
        self.validate()


class TaskScheduler:
    """Select dependency-ready tasks while avoiding resources owned by others."""
    def next_tasks(self, graph: TaskGraph, held_resources: set[str], limit: int = 1) -> tuple[GraphTask, ...]:
        graph.validate()
        selected: list[GraphTask] = []
        reserved = set(held_resources)
        for task in sorted(graph.runnable(), key=lambda item: (-item.priority, item.deadline or datetime.max, item.task_id)):
            if not task.resources & reserved:
                selected.append(task)
                reserved.update(task.resources)
                if len(selected) == limit:
                    break
        return tuple(selected)
