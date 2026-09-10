"""Deterministic, resource-aware team proposals for existing scheduler/runtime."""
from __future__ import annotations
from dataclasses import dataclass
from app.autonomy.task_graph import TaskGraph
from app.autonomy.registry import AgentRegistry
@dataclass(frozen=True, slots=True)
class TeamAssignment: task_id:str; agent_id:str|None; spawn:bool; reason:str
class AgentTeamBuilder:
    def build(self, graph: TaskGraph, registry: AgentRegistry) -> tuple[TeamAssignment,...]:
        result=[]
        for task in graph.tasks.values():
            candidates=[a for a in registry.agents() if task.capabilities.issubset(registry.capabilities_for(a.agent_id)) and task.permissions.issubset(a.permissions) and task.tool in a.available_tools]
            agent=max(candidates,key=lambda a: registry.metrics_for(a.agent_id).success_rate,default=None)
            result.append(TeamAssignment(task.task_id,agent.agent_id if agent else None,agent is None,"reliable specialist" if agent else "no eligible specialist"))
        return tuple(result)
