"""Runtime policy gate for advisory learning artifacts.

This module deliberately does not grant permissions.  It is used by the execution
layer to reject a proposed workflow before it reaches the scheduler.
"""
from __future__ import annotations
from dataclasses import dataclass

from app.learning.core import Skill, SkillStatus


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    allowed: bool
    reason: str


class PolicyEngine:
    """Conservative policy evaluator for skills proposed by the learning layer."""
    def __init__(self, *, max_risk: str = "medium", allow_candidate_execution: bool = False) -> None:
        self.max_risk = max_risk
        self.allow_candidate_execution = allow_candidate_execution

    def evaluate(self, skill: Skill, *, agent_permissions: frozenset[str],
                 available_capabilities: frozenset[str], environment: dict[str, str], goal: str = "",
                 tools: frozenset[str] = frozenset(), available_resources: frozenset[str] = frozenset(),
                 requires_approval: bool = False, approved: bool = False) -> PolicyDecision:
        executable = {SkillStatus.VERIFIED, SkillStatus.TRUSTED}
        if self.allow_candidate_execution:
            executable.add(SkillStatus.TESTED)
        if requires_approval and not approved:
            return PolicyDecision(False, "runtime approval is required")
        declared_tools = {str(step.get("tool")) for step in skill.workflow if step.get("tool")}
        if tools and not declared_tools.issubset(tools):
            return PolicyDecision(False, "skill references unavailable tools")
        required_resources = {resource for step in skill.workflow for resource in step.get("resources", ())}
        if available_resources and not required_resources.issubset(available_resources):
            return PolicyDecision(False, "skill requires unavailable resources")
        if not goal.strip():
            return PolicyDecision(False, "a user goal is required")
        if skill.status not in executable:
            return PolicyDecision(False, f"skill status {skill.status.value} is not executable")
        if not skill.required_permissions.issubset(agent_permissions):
            return PolicyDecision(False, "skill requests permissions not held by the assigned agent")
        if not skill.required_capabilities.issubset(available_capabilities):
            return PolicyDecision(False, "skill requires unavailable capabilities")
        if _risk(skill.risk_level) > _risk(self.max_risk):
            return PolicyDecision(False, "skill risk exceeds the runtime learning policy")
        for key, expected in skill.preconditions.items():
            if environment.get(key) != str(expected):
                return PolicyDecision(False, f"environment precondition failed: {key}")
        return PolicyDecision(True, "advisory skill satisfies runtime learning policy")


def _risk(value: str) -> int:
    return {"low": 0, "medium": 1, "high": 2, "critical": 3}.get(value.casefold(), 99)
