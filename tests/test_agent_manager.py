import asyncio
from pathlib import Path

import pytest

from app.agents.manager import AgentManager
from app.agents.models import AgentStatus, EventType
from app.agents.tools import RiskLevel, ToolRegistry, ToolSpec
from app.agents.runtime_tools import register_runtime_tools
from app.memory.sqlite_memory import SQLiteMemory
from app.safety.permissions import ApprovalMode, ApprovalRequired, Permission, PermissionDenied, PermissionPolicy


def build_manager(policy: PermissionPolicy | None = None) -> tuple[AgentManager, str]:
    registry = ToolRegistry()
    registry.register(ToolSpec("browser.read_title", "Read title", "Reads a browser title",
                               frozenset({Permission.BROWSER_READ.value}), RiskLevel.LOW,
                               lambda arguments: f"title:{arguments['page']}"))
    registry.register(ToolSpec("keyboard.write", "Type text", "Writes keys",
                               frozenset({Permission.KEYBOARD_WRITE.value}), RiskLevel.HIGH,
                               lambda arguments: arguments["text"]))
    registry.register(ToolSpec("filesystem.write", "Write file", "Writes a file",
                               frozenset({Permission.FILESYSTEM_WRITE.value}), RiskLevel.HIGH,
                               lambda arguments: arguments["path"]))
    manager = AgentManager(registry, policy=policy)
    root = manager.create_root("Root", "orchestrator", "Coordinate work", {
        Permission.BROWSER_READ.value, Permission.KEYBOARD_WRITE.value, Permission.FILESYSTEM_WRITE.value,
    })
    return manager, root.agent_id


def test_end_to_end_child_tool_permissions_and_result_collection() -> None:
    async def scenario() -> None:
        manager, root_id = build_manager()
        child = manager.create_agent(root_id, "Research", "researcher", "Read a page", "Read home page",
                                     {Permission.BROWSER_READ.value}, {"browser.read_title"}, {"scope": "home"})

        async def work(agent, supervisor) -> str:
            allowed = await supervisor.execute_tool(agent.agent_id, "browser.read_title", {"page": "home"})
            with pytest.raises(PermissionDenied):
                await supervisor.execute_tool(agent.agent_id, "keyboard.write", {"text": "forbidden"})
            return allowed

        assert await manager.start_agent(root_id, child.agent_id, work) == "title:home"
        assert manager.collect_result(root_id, child.agent_id) == "title:home"
        assert child.status is AgentStatus.COMPLETED
        assert [record.tool_id for record in child.execution_history] == ["browser.read_title"]
        assert any(event.type is EventType.PERMISSION_DENIED and event.agent_id == child.agent_id
                   for event in manager.events)

    asyncio.run(scenario())


def test_hierarchy_task_assignment_and_permission_escalation_are_controlled() -> None:
    manager, root_id = build_manager()
    child = manager.create_agent(root_id, "Reader", "researcher", "Read", permissions={Permission.BROWSER_READ.value})
    manager.assign_task(root_id, child.agent_id, "Read supplied context", {"document": "brief"})
    assert manager.get_agent_tree(root_id)["children"][0]["agent_id"] == child.agent_id
    assert manager.monitor_agent(root_id, child.agent_id).current_task == "Read supplied context"
    with pytest.raises(PermissionDenied, match="Parent does not possess"):
        manager.create_agent(child.agent_id, "Escalator", "child", "Escalate",
                             permissions={Permission.KEYBOARD_WRITE.value})
    assert manager.events[-1].type is EventType.PERMISSION_DENIED


def test_parent_can_grant_and_revoke_only_its_own_child_permissions() -> None:
    manager, root_id = build_manager()
    child = manager.create_agent(root_id, "Reader", "researcher", "Read")
    manager.grant_permission(root_id, child.agent_id, Permission.BROWSER_READ.value)
    assert child.permissions == {Permission.BROWSER_READ.value}
    manager.revoke_permission(root_id, child.agent_id, Permission.BROWSER_READ.value)
    assert child.permissions == set()
    with pytest.raises(PermissionDenied, match="not a direct child"):
        manager.grant_permission(child.agent_id, root_id, Permission.KEYBOARD_WRITE.value)


def test_policy_requires_human_approval_before_high_risk_tool_execution() -> None:
    async def scenario() -> None:
        policy = PermissionPolicy({Permission.FILESYSTEM_WRITE.value: ApprovalMode.REQUIRE_APPROVAL})
        manager, root_id = build_manager(policy)
        child = manager.create_agent(root_id, "Writer", "writer", "Write", permissions={Permission.FILESYSTEM_WRITE.value},
                                     tools={"filesystem.write"})

        async def work(agent, supervisor) -> str:
            await supervisor.execute_tool(agent.agent_id, "filesystem.write", {"path": "out.txt"})
            return "unreachable"

        with pytest.raises(ApprovalRequired):
            await manager.start_agent(root_id, child.agent_id, work)
        assert child.status is AgentStatus.FAILED
        assert child.execution_history == []

    asyncio.run(scenario())


def test_parallel_children_retry_and_termination() -> None:
    async def scenario() -> None:
        manager, root_id = build_manager()
        first = manager.create_agent(root_id, "First", "worker", "Work")
        second = manager.create_agent(root_id, "Second", "worker", "Work")

        async def parallel_work(agent, supervisor) -> str:
            await asyncio.sleep(0)
            return agent.name

        assert await manager.start_parallel(root_id, [first.agent_id, second.agent_id], parallel_work) == ["First", "Second"]

        attempts = 0
        retry = manager.create_agent(root_id, "Retry", "worker", "Retry")

        async def flaky(agent, supervisor) -> str:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise RuntimeError("temporary")
            return "recovered"

        with pytest.raises(RuntimeError, match="temporary"):
            await manager.start_agent(root_id, retry.agent_id, flaky)
        assert await manager.retry_agent(root_id, retry.agent_id, flaky) == "recovered"
        manager.terminate_agent(root_id, retry.agent_id)
        assert retry.status is AgentStatus.TERMINATED

    asyncio.run(scenario())


def test_agent_snapshots_and_permission_denials_are_persisted(tmp_path) -> None:
    manager, root_id = build_manager()
    storage = SQLiteMemory(tmp_path / "memory.db")
    manager._audit_store = storage
    child = manager.create_agent(root_id, "Reader", "researcher", "Read")
    with pytest.raises(PermissionDenied):
        manager.create_agent(child.agent_id, "Escalator", "worker", "Escalate",
                             permissions={Permission.KEYBOARD_WRITE.value})
    assert {record["agent_id"] for record in storage.agent_records()} == {child.agent_id}
    assert storage.agent_events()[0]["event_type"] == EventType.PERMISSION_DENIED.value
    storage.close()


def test_runtime_filesystem_tool_is_permission_gated_and_repository_scoped(tmp_path) -> None:
    async def scenario() -> None:
        registry = ToolRegistry()
        register_runtime_tools(registry, None, tmp_path)
        manager = AgentManager(registry)
        root = manager.create_root("Root", "orchestrator", "Work", {Permission.FILESYSTEM_WRITE.value})
        child = manager.create_agent(root.agent_id, "Writer", "writer", "Write",
                                     permissions={Permission.FILESYSTEM_WRITE.value}, tools={"filesystem.write"})

        async def work(agent, supervisor) -> str:
            return await supervisor.execute_tool(agent.agent_id, "filesystem.write", {"path": "notes/a.txt", "content": "ok"})

        assert Path(await manager.start_agent(root.agent_id, child.agent_id, work)).read_text() == "ok"
        manager.assign_task(root.agent_id, child.agent_id, "Try unsafe path")

        async def unsafe(agent, supervisor) -> str:
            return await supervisor.execute_tool(agent.agent_id, "filesystem.write", {"path": "../unsafe.txt", "content": "no"})

        with pytest.raises(ValueError, match="inside the repository"):
            await manager.start_agent(root.agent_id, child.agent_id, unsafe)

    asyncio.run(scenario())
