"""Safe structured execution summaries; no private reasoning is exposed."""
from __future__ import annotations
from dataclasses import dataclass
from app.learning.core import Experience
from app.learning.evidence import EvidenceStore
@dataclass(frozen=True, slots=True)
class ExecutionExplanation:
    goal:str; strategy:str; agents:tuple[str,...]; verification:tuple[str,...]; recovery:tuple[str,...]; evidence:tuple[str,...]; uncertainty:tuple[str,...]
def explain(experience: Experience, evidence: EvidenceStore) -> ExecutionExplanation:
    refs=tuple(item.reference for claim in experience.verification_results for item in evidence.for_claim(claim))
    uncertainty=tuple(experience.failures) or (() if experience.verified else ("Final verification did not pass",))
    return ExecutionExplanation(experience.goal, str(experience.plan.get("workflow", ())), experience.agents_used, experience.verification_results, experience.recovery_steps, refs, uncertainty)
