"""Bounded action accounting for every provider/browser operation."""
from __future__ import annotations


class ActionLimitExceeded(RuntimeError):
    """Raised before an operation would exceed the configured action budget."""


class ActionManager:
    def __init__(self, max_actions: int) -> None:
        self.max_actions = max_actions
        self.count = 0

    def record(self, description: str) -> None:
        if self.count >= self.max_actions:
            raise ActionLimitExceeded(f"Action limit of {self.max_actions} reached before {description}")
        self.count += 1
