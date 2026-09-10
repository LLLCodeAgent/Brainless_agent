"""Availability and reliability-aware registry for reusable configured agents."""
from __future__ import annotations

from dataclasses import dataclass
from app.agents.models import Agent, AgentStatus
from app.autonomy.models import TaskRequirements


@dataclass(slots=True)
class ReliabilityMetrics:
    successes: int = 0
    failures: int = 0
    verification_failures: int = 0
    retries: int = 0
    permission_denials: int = 0
    resource_conflicts: int = 0
    total_duration_ms: float = 0.0

    @property
    def success_rate(self) -> float:
        total = self.successes + self.failures
        return self.successes / total if total else 1.0

    @property
    def average_duration_ms(self) -> float:
        total = self.successes + self.failures
        return self.total_duration_ms / total if total else 0.0


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, Agent] = {}
        self._capabilities: dict[str, frozenset[str]] = {}
        self._metrics: dict[str, ReliabilityMetrics] = {}

    def register(self, agent: Agent, capabilities: frozenset[str]) -> None:
        self._agents[agent.agent_id] = agent
        self._capabilities[agent.agent_id] = capabilities
        self._metrics.setdefault(agent.agent_id, ReliabilityMetrics())

    def retire(self, agent_id: str) -> None:
        self._agents.pop(agent_id, None)
        self._capabilities.pop(agent_id, None)

    def find(self, requirements: TaskRequirements) -> Agent | None:
        candidates = [agent for agent_id, agent in self._agents.items()
                      if agent.status in {AgentStatus.READY, AgentStatus.COMPLETED}
                      and requirements.capabilities.issubset(self._capabilities[agent_id])
                      and requirements.permissions.issubset(agent.permissions)
                      and requirements.tools.issubset(agent.available_tools)]
        return max(candidates, key=lambda agent: self._metrics[agent.agent_id].success_rate, default=None)

    def record_result(self, agent_id: str, *, success: bool, duration_ms: float,
                      verified: bool = True, retry: bool = False, permission_denied: bool = False,
                      resource_conflict: bool = False) -> None:
        metrics = self._metrics[agent_id]
        metrics.successes += int(success)
        metrics.failures += int(not success)
        metrics.total_duration_ms += duration_ms
        metrics.verification_failures += int(success and not verified)
        metrics.retries += int(retry)
        metrics.permission_denials += int(permission_denied)
        metrics.resource_conflicts += int(resource_conflict)

    def metrics_for(self, agent_id: str) -> ReliabilityMetrics:
        return self._metrics[agent_id]

    def capabilities_for(self, agent_id: str) -> frozenset[str]: return self._capabilities[agent_id]
    def search_by_role(self, role: str) -> tuple[Agent, ...]: return tuple(agent for agent in self._agents.values() if agent.role == role)
    def available(self, agent_id: str) -> bool: return self._agents[agent_id].status in {AgentStatus.READY, AgentStatus.COMPLETED}
    def agents(self) -> tuple[Agent, ...]: return tuple(self._agents.values())
