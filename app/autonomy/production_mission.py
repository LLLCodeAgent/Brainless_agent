"""Production composition of persisted missions and the verified task engine."""
from __future__ import annotations

from app.autonomy.mission import Mission
from app.autonomy.task_graph import GraphTask, TaskGraph
from app.autonomy.task_runner import TaskEngineMissionRunner


class VerifiedMissionCriterion:
    """Requires at least one successful runtime-audited action for this mission."""
    def __init__(self, actions, mission_id: str) -> None:
        self.actions, self.mission_id = actions, mission_id

    async def verify(self, _) -> tuple[bool, str]:
        records = [item for item in self.actions.audit if item.task_id.startswith(self.mission_id)]
        passed = bool(records) and records[-1].error is None
        return passed, "No verified runtime action completed for the mission"


class RuntimeMissionComposer:
    """Builds a least-privilege single-objective graph from runtime analysis."""
    def __init__(self, autonomous, task_engine, root_agent_id: str) -> None:
        self.autonomous, self.actions = autonomous, autonomous.actions
        self.runner = TaskEngineMissionRunner(task_engine, root_agent_id, self.graph_for,
                                               lambda _: None, self.criteria_for)

    def graph_for(self, mission: Mission) -> TaskGraph:
        requirements = self.autonomous.analyzer.analyze(mission.goal)
        graph = TaskGraph()
        previous = None
        for index, tool_id in enumerate(sorted(requirements.tools)):
            tool = self.actions.manager.tools.get(tool_id)
            task_id = f"objective:{index}"
            graph.add(GraphTask(task_id, mission.goal,
                                dependencies={previous} if previous else set(),
                                capabilities=requirements.capabilities,
                                permissions=tool.required_permissions,
                                resources=frozenset({tool_id.split(".")[0]}),
                                tool=tool_id, priority=mission.priority))
            previous = task_id
        if not graph.tasks:
            raise ValueError("Mission requires no executable capability; user clarification is required")
        return graph

    def criteria_for(self, mission: Mission):
        return (VerifiedMissionCriterion(self.actions, mission.mission_id),)

    async def __call__(self, mission: Mission):
        return await self.runner(mission)
