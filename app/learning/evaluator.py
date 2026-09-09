"""Structured execution evaluation and conservative candidate-skill extraction."""
from __future__ import annotations
from dataclasses import dataclass
from app.learning.core import Experience, Skill

@dataclass(frozen=True, slots=True)
class ExecutionReview:
    success_rate: float
    verification_rate: float
    failure_count: int
    recovery_count: int
    unnecessary_permissions: tuple[str, ...]
    recommendation: str

class ExecutionEvaluator:
    def review(self, experience: Experience) -> ExecutionReview:
        used = set(experience.capabilities_used) | set(experience.tools_used)
        declared = set(experience.plan.get("declared_permissions", ()))
        unnecessary = tuple(sorted(declared - used))
        return ExecutionReview(float(experience.success), float(experience.verified), len(experience.failures),
            len(experience.recovery_steps), unnecessary,
            "candidate skill eligible" if experience.success and experience.verified and not experience.failures else "retain as contextual failure knowledge")

    def candidate(self, experience: Experience, name: str, description: str) -> Skill | None:
        review = self.review(experience)
        workflow = tuple(experience.plan.get("workflow", ()))
        if review.recommendation != "candidate skill eligible" or not workflow: return None
        return Skill(name, description, frozenset(experience.capabilities_used), frozenset(experience.plan.get("declared_permissions", ())),
                     workflow, tuple(experience.plan.get("expected_outcomes", ())), source_experience_id=experience.experience_id,
                     evaluation={"success_rate": review.success_rate, "verification_rate": review.verification_rate})
