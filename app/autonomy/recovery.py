"""Failure classification and safety-aware recovery decisions."""
from __future__ import annotations
from enum import Enum
from app.autonomy.contracts import Idempotency
from app.autonomy.models import ErrorCode

class RecoveryStrategy(str, Enum):
    RETRY="retry"; REOBSERVE="reobserve"; ALTERNATIVE_TARGET="alternative_target"; REPLAN="replan"; HUMAN_APPROVAL="human_approval"; ABORT="abort"

class RecoveryEngine:
    def choose(self, error: str | None, idempotency: Idempotency, attempts: int, max_attempts: int) -> RecoveryStrategy:
        code = (error or "").split(":", 1)[0]
        if code in {ErrorCode.PERMISSION_DENIED.value, ErrorCode.POLICY_DENIED.value, ErrorCode.APPROVAL_REQUIRED.value}:
            return RecoveryStrategy.HUMAN_APPROVAL
        if code in {ErrorCode.VERIFICATION_FAILED.value, ErrorCode.ACTION_FAILED.value}:
            return RecoveryStrategy.REOBSERVE if idempotency is Idempotency.NOT_SAFE_TO_RETRY else RecoveryStrategy.RETRY
        if code == ErrorCode.INVALID_ARGUMENT.value: return RecoveryStrategy.REPLAN
        return RecoveryStrategy.RETRY if idempotency is Idempotency.SAFE_TO_RETRY and attempts < max_attempts else RecoveryStrategy.ABORT
