"""Bridge advisory experience/skills into the existing validated task-engine path."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from app.autonomy.planning import PlanValidator
from app.autonomy.task_graph import TaskGraph
from app.learning.core import Experience, ExperienceMemory, Skill, SkillRegistry, SkillStatus, WorkflowSynthesizer
from app.learning.evaluator import ExecutionEvaluator

@dataclass(frozen=True, slots=True)
class LearningConfig:
    learning_enabled: bool = True
    experience_retrieval_enabled: bool = True
    skill_learning_enabled: bool = True
    skill_auto_activation: bool = False
    minimum_skill_success_rate: float = .8
    max_candidate_skills: int = 20
    require_human_approval_for_skill_activation: bool = True

@dataclass(frozen=True, slots=True)
class WorkflowAdvice:
    experiences: tuple[Experience, ...]
    skills: tuple[Skill, ...]
    graph: TaskGraph

class SkillSandbox:
    """Static sandbox gate; it validates a candidate but never executes or activates it."""
    def validate(self, skill: Skill, *, capabilities: frozenset[str], permissions: frozenset[str],
                 known_tools: frozenset[str], contracted_tools: frozenset[str]) -> None:
        if skill.status is not SkillStatus.CANDIDATE:
            raise ValueError("Only candidate skills may enter the sandbox")
        graph = WorkflowSynthesizer().synthesize(skill.description, [skill])
        PlanValidator().validate(graph, available_capabilities=capabilities, available_permissions=permissions,
                                 known_tools=known_tools, contracted_tools=contracted_tools)

class LearningCoordinator:
    """Retrieves advisory knowledge and persists evaluated runtime outcomes.

    It never invokes a controller or changes permissions/statuses: callers still send
    the graph through the existing plan validator and AutonomousTaskEngine.
    """
    def __init__(self, experiences: ExperienceMemory, skills: SkillRegistry,
                 config: LearningConfig | None = None) -> None:
        self.experiences, self.skills, self.config = experiences, skills, config or LearningConfig()

    def advise(self, goal: str, task_type: str, environment: dict[str, str]) -> WorkflowAdvice:
        experiences = self.experiences.retrieve(goal, task_type=task_type, environment=environment) if self.config.experience_retrieval_enabled else []
        skills = self.skills.search(goal) if self.config.learning_enabled else []
        return WorkflowAdvice(tuple(experiences), tuple(skills), WorkflowSynthesizer().synthesize(goal, skills, experiences))

    def record(self, experience: Experience, *, candidate_name: str | None = None,
               candidate_description: str | None = None) -> Skill | None:
        self.experiences.store(experience)
        if not self.config.skill_learning_enabled or not candidate_name or not candidate_description:
            return None
        candidate = ExecutionEvaluator().candidate(experience, candidate_name, candidate_description)
        if candidate is None: return None
        if len(self.skills.candidates()) >= self.config.max_candidate_skills: return None
        self.skills.register(candidate)
        return candidate
