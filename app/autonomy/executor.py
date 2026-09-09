"""Runtime-owned observation, execution, verification, and recovery loop."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from time import monotonic
from typing import Any, Protocol

from app.agents.manager import AgentManager
from app.agents.tools import RiskLevel, ToolSpec
from app.autonomy.controllers import ComputerController
from app.autonomy.config import AutonomyLimits
from app.autonomy.contracts import ActionContract
from app.autonomy.world_state import WorldStateManager
from app.autonomy.models import (ActionProposal, ActionResult, AuditRecord, ComputerAction,
                                 ComputerState, DecisionContext, ErrorCode, RuntimeErrorDetail)
from app.autonomy.resources import ResourceLockManager
from app.autonomy.contracts import Idempotency
from app.autonomy.recovery import RecoveryEngine, RecoveryStrategy
from app.safety.permissions import ApprovalRequired, PermissionDenied


class DecisionProvider(Protocol):
    async def next_action(self, context: DecisionContext) -> ActionProposal | None: ...


ApprovalHandler = Callable[[ComputerAction], Awaitable[bool] | bool]
Verifier = Callable[[dict[str, Any], ComputerState, Any], bool]


class ActionRuntime:
    """The only computer-action authority; reasoning can only submit proposals."""
    def __init__(self, manager: AgentManager, controller: ComputerController,
                 locks: ResourceLockManager | None = None, verifier: Verifier | None = None,
                 approval_handler: ApprovalHandler | None = None, audit_store=None,
                 world_state: WorldStateManager | None = None,
                 contracts: dict[str, ActionContract] | None = None,
                 recovery: RecoveryEngine | None = None,
                 limits: AutonomyLimits | None = None, journal=None) -> None:
        self.manager, self.controller = manager, controller
        self.locks, self.verifier = locks or ResourceLockManager(), verifier or _verify
        self.world_state, self.contracts = world_state or WorldStateManager(), contracts or {}
        self.recovery, self.recovery_events = recovery or RecoveryEngine(), []
        self.limits = limits or AutonomyLimits()
        self.journal = journal
        self.approval_handler, self.audit, self._audit_store = approval_handler, [], audit_store
        self._register_controller_tools()

    def _register_controller_tools(self) -> None:
        definitions = {
            "browser.navigate": ("browser.navigate", ("url",), {"browser", "screen"}),
            "mouse.click": ("mouse.click", ("x", "y"), {"mouse", "screen"}),
            "keyboard.write": ("keyboard.write", ("text",), {"keyboard"}),
            "filesystem.write": ("filesystem.write", ("path", "content"), {"filesystem"}),
            "filesystem.read": ("filesystem.read", ("path",), {"filesystem"}),
            "filesystem.exists": ("filesystem.read", ("path",), {"filesystem"}),
            "process.execute": ("process.execute", ("command",), {"process"}),
        }
        self._resources: dict[str, set[str]] = {}
        for tool_id, (permission, schema, resources) in definitions.items():
            self._resources[tool_id] = resources
            if not self.manager.tools.contains(tool_id):
                async def handler(arguments: dict[str, Any], action_type: str = tool_id) -> Any:
                    return await self.controller.execute(action_type, arguments)
                self.manager.tools.register(ToolSpec(tool_id, tool_id, "Runtime-controlled computer action",
                    frozenset({permission}), RiskLevel.HIGH, handler, schema, category="computer"))

    async def perform_proposal(self, agent_id: str, task_id: str, proposal: ActionProposal) -> ActionResult:
        try:
            tool = self.manager.tools.get(proposal.action_type)
        except KeyError:
            action = ComputerAction(proposal.action_type, proposal.arguments, agent_id, task_id, proposal.reason, "")
            return self._result(action, False, "Tool is not registered", monotonic(), ErrorCode.TOOL_NOT_FOUND)
        if len(tool.required_permissions) != 1:
            action = ComputerAction(proposal.action_type, proposal.arguments, agent_id, task_id, proposal.reason, "")
            return self._result(action, False, "Computer actions require one declared permission", monotonic(), ErrorCode.INVALID_ARGUMENT)
        action = ComputerAction(proposal.action_type, proposal.arguments, agent_id, task_id, proposal.reason,
                                next(iter(tool.required_permissions)), proposal.expected_state)
        return await self.perform(action)

    async def perform(self, action: ComputerAction) -> ActionResult:
        started = monotonic()
        self._journal(action.task_id, "ACTION_STARTED", {"action_id": action.action_id, "tool": action.action_type})
        policy_decision, approval_status = "auto_approve", "not_required"
        try:
            tool = self.manager.tools.get(action.action_type)
        except KeyError:
            return self._result(action, False, "Tool is not registered", started, ErrorCode.TOOL_NOT_FOUND)
        if action.permission not in tool.required_permissions:
            return self._result(action, False, "Action permission does not match registered tool", started, ErrorCode.INVALID_ARGUMENT)
        contract = self.contracts.get(action.action_type)
        if contract:
            if contract.tool != action.action_type or action.permission not in contract.required_permissions:
                return self._result(action, False, "Action violates its registered contract", started, ErrorCode.INVALID_ARGUMENT)
            try:
                pre_state = await self.controller.observe()
                self.world_state.capture(pre_state, source="precondition")
                contract.validate(pre_state, action.permission)
            except ValueError as error:
                return self._result(action, False, str(error), started, ErrorCode.INVALID_ARGUMENT)
        try:
            self.manager.policy.check(action.agent_id, action.permission)
        except ApprovalRequired as error:
            policy_decision, approval_status = "require_approval", "required"
            if self.approval_handler is None:
                return self._result(action, False, str(error), started, ErrorCode.APPROVAL_REQUIRED,
                                    policy=policy_decision, approval=approval_status)
            approved = self.approval_handler(action)
            if hasattr(approved, "__await__"):
                approved = await approved
            if not approved:
                return self._result(action, False, "Approval denied", started, ErrorCode.POLICY_DENIED,
                                    policy="deny", approval="denied")
            self.manager.policy.approve_once(action.agent_id, action.permission)
            approval_status = "approved"
        except PermissionDenied as error:
            return self._result(action, False, str(error), started, ErrorCode.POLICY_DENIED, policy="deny")
        try:
            async with self.locks.acquire(action.agent_id, self._resources.get(action.action_type, {action.action_type.split('.')[0]})):
                # AgentManager enforces allow-list, permission, policy, schema, and records the tool event.
                before = await self.controller.observe()
                before_snapshot = self.world_state.capture(before, source="before_action", evidence=action.action_id)
                self._journal(action.task_id, "OBSERVATION_CAPTURED", {"action_id": action.action_id, "phase": "before", "world_version": before_snapshot.version})
                if contract and contract.timeout_seconds is not None:
                    async with asyncio.timeout(contract.timeout_seconds):
                        output = await self.manager.execute_tool(action.agent_id, action.action_type, action.arguments)
                else:
                    output = await self.manager.execute_tool(action.agent_id, action.action_type, action.arguments)
                observed = await self.controller.observe()
                after_snapshot = self.world_state.capture(observed, source="after_action", evidence=action.action_id)
                self._journal(action.task_id, "OBSERVATION_CAPTURED", {"action_id": action.action_id, "phase": "after", "world_version": after_snapshot.version})
        except PermissionDenied as error:
            return self._result(action, False, str(error), started, ErrorCode.PERMISSION_DENIED,
                                policy=policy_decision, approval=approval_status)
        except ValueError as error:
            return self._result(action, False, str(error), started, ErrorCode.INVALID_ARGUMENT,
                                policy=policy_decision, approval=approval_status)
        except RuntimeErrorDetail as error:
            return self._result(action, False, str(error), started, error.code,
                                policy=policy_decision, approval=approval_status)
        except TimeoutError as error:
            return self._result(action, False, str(error) or "Action timed out", started, ErrorCode.ACTION_TIMEOUT,
                                policy=policy_decision, approval=approval_status)
        except Exception as error:
            return self._result(action, False, str(error), started, ErrorCode.ACTION_FAILED,
                                policy=policy_decision, approval=approval_status)
        expected = {key: value for key, value in action.expected_state.items() if key != "state_changed"}
        if contract:
            expected = {**contract.expected_effects, **expected}
        verified = self.verifier(expected, observed, output)
        if action.expected_state.get("state_changed"):
            verified = verified and bool(self.world_state.diff(before_snapshot, after_snapshot))
        return self._result(action, verified, None if verified else "Expected state was not observed", started,
                            None if verified else ErrorCode.VERIFICATION_FAILED, output, verified,
                            policy=policy_decision, approval=approval_status)

    async def run_loop(self, agent_id: str, task_id: str, task: str, decider: DecisionProvider,
                       *, max_steps: int | None = None, max_failures: int | None = None) -> list[ActionResult]:
        max_steps = self.limits.max_steps if max_steps is None else max_steps
        max_failures = self.limits.max_recovery_attempts if max_failures is None else max_failures
        results: list[ActionResult] = []
        failures = 0
        for _ in range(max_steps):
            state = await self.controller.observe()
            self.world_state.capture(state, source="loop_observation")
            proposal = await decider.next_action(DecisionContext(agent_id, task_id, task,
                state.compact({"browser_url", "browser_title", "visible_ui", "progress"}), results[-1] if results else None))
            if proposal is None:
                return results
            result = await self.perform_proposal(agent_id, task_id, proposal)
            results.append(result)
            failures = failures + 1 if not result.success else 0
            contract = self.contracts.get(proposal.action_type)
            if not result.success and contract:
                strategy = self.recovery.choose(result.error, contract.idempotency, failures, contract.retry.max_attempts)
                self.recovery_events.append((result.action_id, strategy.value))
                # Retry only a contract explicitly classified as safe, and always observe again first.
                if strategy is RecoveryStrategy.RETRY and contract.idempotency is Idempotency.SAFE_TO_RETRY and failures < contract.retry.max_attempts:
                    retry_state = await self.controller.observe()
                    self.world_state.capture(retry_state, source="recovery_reobserve", evidence=result.action_id)
                    retry = await self.perform_proposal(agent_id, task_id, proposal)
                    results.append(retry)
                    failures = failures + 1 if not retry.success else 0
            if failures > max_failures:
                raise RuntimeErrorDetail(ErrorCode.ACTION_FAILED, "Failure budget exhausted")
        raise RuntimeErrorDetail(ErrorCode.ACTION_TIMEOUT, "Step budget exhausted")

    def _result(self, action: ComputerAction, success: bool, error: str | None, started: float,
                code: ErrorCode | None = None, output: Any = None, verified: bool = False,
                policy: str = "auto_approve", approval: str = "not_required") -> ActionResult:
        result = ActionResult(action.action_id, success, output, f"{code.value}: {error}" if code else error, verified,
                              (monotonic() - started) * 1000)
        agent = self.manager.get_agent(action.agent_id)
        record = AuditRecord(action.timestamp, action.agent_id, agent.parent_agent_id, action.task_id, action.action_id,
            action.action_type, action.permission, _redact_arguments(action.arguments), str(output) if output is not None else None,
            result.error, result.duration_ms, policy, approval)
        self.audit.append(record)
        if self._audit_store:
            self._audit_store.store_action_audit(record)
        self._journal(action.task_id, "VERIFICATION_PASSED" if verified else "VERIFICATION_FAILED",
                      {"action_id": action.action_id, "error": result.error})
        return result

    def _journal(self, task_id: str, event: str, detail: dict[str, object]) -> None:
        if self.journal:
            self.journal.store_task_journal(task_id, event, detail)


def _verify(expected: dict[str, Any], state: ComputerState, output: Any) -> bool:
    return not expected or all(getattr(state, key, None) == value for key, value in expected.items())


def _redact_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    """Audit capability references, never secret material supplied by a tool caller."""
    sensitive = {"password", "secret", "token", "api_key", "authorization", "cookie"}
    return {key: "[REDACTED]" if any(part in key.casefold() for part in sensitive) else value
            for key, value in arguments.items()}
