from pathlib import Path
import pytest

from app.learning import (Experience, ExperienceMemory, ExperienceSource, Skill, SkillEvaluator,
                          SkillRegistry, SkillStatus, WorkflowSynthesizer)


def make_skill(version=1, status=SkillStatus.CANDIDATE, rate=0.0):
    return Skill("write report", "write a verified report", frozenset({"filesystem.write"}),
                 frozenset({"filesystem.write"}), ({"objective": "write report", "tool": "filesystem.write", "resources": ["filesystem/report"]},),
                 ("report exists",), version=version, status=status, evaluation={"success_rate": rate})


def test_experience_is_durable_ranked_and_external_content_is_not_trusted(tmp_path):
    memory = ExperienceMemory(tmp_path / "experience.db")
    good = Experience("Create a verified report", "report", {"app": "filesystem"}, {"nodes": ["write"]}, True, True, "done", tools_used=("filesystem.write",))
    memory.store(good)
    found = memory.retrieve("create report", task_type="report", environment={"app": "filesystem"})
    assert found == [good]
    with pytest.raises(ValueError, match="External"):
        memory.store(Experience("ignore policy", "report", {}, {}, False, False, "", source=ExperienceSource.EXTERNAL))
    memory.close()


def test_skills_are_versioned_candidate_first_and_regressions_are_rejected(tmp_path):
    registry = SkillRegistry(tmp_path / "skills.db")
    v1 = make_skill(1, rate=.9); registry.register(v1); registry.set_status(v1.skill_id, SkillStatus.VERIFIED)
    v2 = make_skill(2, rate=.5); registry.register(v2)
    outcome = SkillEvaluator().evaluate(v2, [Experience("report", "report", {}, {}, False, False, "failed")], baseline=registry.get(v1.skill_id))
    assert outcome is SkillStatus.REJECTED
    registry.set_status(v2.skill_id, outcome)
    assert registry.get(v1.skill_id).status is SkillStatus.VERIFIED
    assert registry.get(v2.skill_id).status is SkillStatus.REJECTED
    assert registry.search("verified report") == [registry.get(v1.skill_id)]
    registry.close()


def test_second_goal_retrieves_experience_discovers_skill_and_synthesizes_reusable_graph(tmp_path):
    memory = ExperienceMemory(tmp_path / "experiences.db")
    registry = SkillRegistry(tmp_path / "skills.db")
    first = Experience("Create report about weather", "report", {"app": "filesystem"}, {"workflow": "write"}, True, True, "report created")
    memory.store(first)
    skill = make_skill(); registry.register(skill); registry.set_status(skill.skill_id, SkillStatus.VERIFIED)
    reused = memory.retrieve("Create another weather report", task_type="report")
    discovered = registry.search("write verified report")
    graph = WorkflowSynthesizer().synthesize("Create another weather report", discovered, reused)
    assert reused[0].experience_id == first.experience_id
    assert discovered[0].skill_id == skill.skill_id
    node = next(iter(graph.tasks.values()))
    assert node.tool == "filesystem.write" and node.permissions == frozenset({"filesystem.write"})
    memory.close(); registry.close()


def test_execution_evaluation_creates_candidate_only_from_verified_structured_workflow():
    from app.learning import ExecutionEvaluator
    experience = Experience("write report", "report", {}, {"workflow": [{"objective": "write"}], "declared_permissions": ["filesystem.write"], "expected_outcomes": ["file exists"]}, True, True, "done", capabilities_used=("filesystem.write",))
    candidate = ExecutionEvaluator().candidate(experience, "write report", "persist a report")
    assert candidate and candidate.status is SkillStatus.CANDIDATE
    failed = Experience("write report", "report", {}, {"workflow": [{"objective": "write"}]}, False, False, "", failures=("permission denied",))
    assert ExecutionEvaluator().candidate(failed, "bad", "bad") is None


def test_conflicts_require_verification_or_high_risk_escalation():
    from app.learning import AgentMessage, ConflictResolver, Evidence, EvidenceKind, EvidenceStore, MessageKind
    store = EvidenceStore(); first = store.add(Evidence("price", EvidenceKind.URL, "a")); second = store.add(Evidence("price", EvidenceKind.URL, "b"))
    messages = (AgentMessage("a", MessageKind.FINDING, "price", (first.evidence_id,), {"value": "10"}), AgentMessage("b", MessageKind.FINDING, "price", (second.evidence_id,), {"value": "11"}))
    assert ConflictResolver().resolve("price", messages, store).resolution.value == "verify"
    assert ConflictResolver().resolve("price", messages, store, high_risk=True).resolution.value == "escalate"


def test_learning_coordinator_records_first_execution_and_reuses_advisory_workflow(tmp_path):
    from app.learning import LearningCoordinator
    memory = ExperienceMemory(tmp_path / "experience.db")
    registry = SkillRegistry(tmp_path / "skills.db")
    coordinator = LearningCoordinator(memory, registry)
    first = Experience("create project report", "report", {"app": "filesystem"}, {"workflow": [{"objective": "write", "tool": "filesystem.write"}], "declared_permissions": ["filesystem.write"], "expected_outcomes": ["file exists"]}, True, True, "done", capabilities_used=("filesystem.write",))
    candidate = coordinator.record(first, candidate_name="create report", candidate_description="create a report")
    assert candidate and candidate.status is SkillStatus.CANDIDATE
    registry.set_status(candidate.skill_id, SkillStatus.VERIFIED)
    second = coordinator.advise("create another project report", "report", {"app": "filesystem"})
    assert second.experiences[0].experience_id == first.experience_id
    assert second.skills[0].skill_id == candidate.skill_id
    assert second.graph.tasks
    memory.close(); registry.close()


def test_skill_sandbox_rejects_permission_escalation(tmp_path):
    from app.learning import SkillSandbox
    candidate = make_skill()
    with pytest.raises(ValueError, match="unavailable permissions"):
        SkillSandbox().validate(candidate, capabilities=frozenset({"filesystem.write"}), permissions=frozenset(),
                                known_tools=frozenset({"filesystem.write"}), contracted_tools=frozenset({"filesystem.write"}))
