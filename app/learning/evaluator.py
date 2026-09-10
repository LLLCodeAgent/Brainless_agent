"""Structured evaluation and conservative candidate-skill extraction."""
from __future__ import annotations
from dataclasses import dataclass
from statistics import mean
from app.learning.core import Experience, Skill, SkillStatus

@dataclass(frozen=True, slots=True)
class ExecutionReview:
    success_rate: float
    verification_rate: float
    failure_count: int
    recovery_count: int
    unnecessary_permissions: tuple[str, ...]
    recommendation: str
    average_execution_ms: float = 0.0
    average_resource_cost: float = 0.0
    repeatable: bool = False

class ExecutionEvaluator:
    def review(self, experience: Experience) -> ExecutionReview:
        used = set(experience.capabilities_used) | set(experience.tools_used)
        declared = set(experience.plan.get("declared_permissions", ()))
        return ExecutionReview(float(experience.success), float(experience.verified), len(experience.failures),
            len(experience.recovery_steps), tuple(sorted(declared - used)),
            "candidate skill eligible" if experience.success and experience.verified and not experience.failures else "retain as contextual failure knowledge",
            experience.execution_time_ms, sum(experience.resource_usage.values()), experience.success and experience.verified)

    def metrics(self, experiences: list[Experience]) -> dict[str, float]:
        if not experiences: return {"success_rate": 0.0}

        successes = [item for item in experiences if item.success]
        verified = [item for item in experiences if item.success and item.verified]
        metrics = {"success_rate": len(successes) / len(experiences), "verification_rate": len(verified) / len(experiences),
                   "failure_rate": 1 - len(successes) / len(experiences),
                   "recovery_rate": mean(len(item.recovery_steps) for item in experiences),
                   "execution_time_ms": mean(item.execution_time_ms for item in experiences),
                   "resource_cost": mean(sum(item.resource_usage.values()) for item in experiences),
                   "repeatability": float(len(verified) >= 2)}
        return metrics

    def evaluate(self, skill: Skill, experiences: list[Experience], *, baseline: Skill | None = None) -> SkillStatus:
        metrics = self.metrics(experiences)
        if baseline and metrics["success_rate"] < baseline.evaluation.get("success_rate", 0.0): return SkillStatus.REJECTED
        return SkillStatus.TESTED if metrics.get("verification_rate", 0.0) >= .8 else SkillStatus.REJECTED

    def candidate(self, experience: Experience, name: str, description: str) -> Skill | None:
        review = self.review(experience); workflow = tuple(experience.plan.get("workflow", ()))
        if review.recommendation != "candidate skill eligible" or not workflow: return None
        return Skill(name, description, frozenset(experience.capabilities_used), frozenset(experience.plan.get("declared_permissions", ())),
                     workflow, tuple(experience.plan.get("expected_outcomes", ())), source_experience_id=experience.experience_id,
                     evaluation={"success_rate": review.success_rate, "verification_rate": review.verification_rate},
                     success_metrics={"execution_time_ms": review.average_execution_ms, "resource_cost": review.average_resource_cost})
