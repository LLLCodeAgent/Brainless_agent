"""Safe runtime limits for autonomous execution."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class AutonomyLimits:
    max_agent_depth: int = 4
    max_child_agents: int = 16
    max_parallel_agents: int = 4
    max_task_retries: int = 2
    max_recovery_attempts: int = 2
    max_steps: int = 12
    verification_timeout_seconds: float = 30.0
    resource_lock_timeout_seconds: float = 30.0
    task_timeout_seconds: float = 600.0
    target_confidence_threshold: float = 0.75
