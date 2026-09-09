"""Availability-aware registry for reusable configured agents."""
from __future__ import annotations

from app.agents.models import Agent, AgentStatus
from app.autonomy.models import TaskRequirements


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, Agent] = {}
        self._capabilities: dict[str, frozenset[str]] = {}

    def register(self, agent: Agent, capabilities: frozenset[str]) -> None:
        self._agents[agent.agent_id] = agent
        self._capabilities[agent.agent_id] = capabilities

    def find(self, requirements: TaskRequirements) -> Agent | None:
        candidates = (agent for agent_id, agent in self._agents.items()
                      if agent.status in {AgentStatus.READY, AgentStatus.COMPLETED}
                      and requirements.capabilities.issubset(self._capabilities[agent_id])
                      and requirements.permissions.issubset(agent.permissions)
                      and requirements.tools.issubset(agent.available_tools))
        return next(candidates, None)

    def capabilities_for(self, agent_id: str) -> frozenset[str]:
        return self._capabilities[agent_id]

    def search_by_role(self, role: str) -> tuple[Agent, ...]:
        return tuple(agent for agent in self._agents.values() if agent.role == role)

    def available(self, agent_id: str) -> bool:
        return self._agents[agent_id].status in {AgentStatus.READY, AgentStatus.COMPLETED}

    def agents(self) -> tuple[Agent, ...]:
        return tuple(self._agents.values())
