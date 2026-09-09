"""Deterministic task creation and workflow selection without model inference."""
from __future__ import annotations

from app.tasks.task import Task
from app.tasks.task_parser import parse_task


class TaskManager:
    def __init__(self, available_providers: tuple[str, ...]) -> None:
        self.available_providers = available_providers

    def create(self, objective: str, providers: list[str] | None = None,
               strategy: str = "automatic", prompt_profile: str | None = None) -> Task:
        if not objective.strip():
            raise ValueError("Task objective cannot be empty")
        selected = providers or list(self.available_providers)
        if not selected:
            raise ValueError("Select at least one enabled provider")
        unknown = set(selected) - set(self.available_providers)
        if unknown:
            raise ValueError(f"Unknown or disabled providers: {', '.join(sorted(unknown))}")
        if len(set(selected)) != len(selected):
            raise ValueError("Select each provider at most once")
        task = parse_task(objective, tuple(selected))
        task.providers = selected
        if strategy == "single":
            task.providers = [selected[0]]
            task.strategy, task.synthesis, task.synthesis_provider = "single_provider", False, None
        elif strategy == "multi":
            if len(selected) < 2:
                raise ValueError("Multi-provider strategy requires at least two providers")
            task.strategy = "multi_provider"
            task.synthesis = True
            task.synthesis_provider = "chatgpt" if "chatgpt" in selected else selected[0]
        elif strategy == "automatic" and len(selected) > 1:
            # Checked providers in the GUI are an explicit workflow selection.
            task.strategy = "multi_provider"
            task.synthesis = True
            task.synthesis_provider = "chatgpt" if "chatgpt" in selected else selected[0]
        elif strategy != "automatic":
            raise ValueError(f"Unsupported strategy: {strategy}")
        task.prompt_profile = prompt_profile or task.category
        return task
