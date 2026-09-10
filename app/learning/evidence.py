"""Evidence, calibrated confidence, and evidence-first conflict resolution."""
from __future__ import annotations
import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from uuid import uuid4
class Confidence(str, Enum): UNKNOWN="unknown"; LOW="low"; MEDIUM="medium"; HIGH="high"
class EvidenceKind(str, Enum): URL="url"; FILE="file"; SCREENSHOT="screenshot"; TOOL_RESULT="tool_result"; OBSERVATION="observation"; VERIFICATION="verification"
class MessageKind(str, Enum): FINDING="finding"; EVIDENCE="evidence"; REQUEST="request"; RESULT="result"; WARNING="warning"; BLOCKER="blocker"; DEPENDENCY="dependency"; VERIFICATION="verification"
@dataclass(frozen=True, slots=True)
class Evidence:
    claim: str; kind: EvidenceKind; reference: str; confidence: Confidence = Confidence.UNKNOWN; agent_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc)); evidence_id: str = field(default_factory=lambda: str(uuid4()))
@dataclass(frozen=True, slots=True)
class AgentMessage:
    sender: str; kind: MessageKind; subject: str; evidence_ids: tuple[str, ...] = (); payload: dict[str, str] = field(default_factory=dict)
class EvidenceStore:
    def __init__(self, path: Path | None = None) -> None:
        self._items: dict[str, Evidence] = {}; self.db = sqlite3.connect(path) if path else None
        if self.db: self.db.execute("CREATE TABLE IF NOT EXISTS evidence (id TEXT PRIMARY KEY, payload TEXT NOT NULL)"); self.db.commit(); self._load()
    def _load(self) -> None:
        for row in self.db.execute("SELECT payload FROM evidence"):
            item=json.loads(row[0]); item["kind"]=EvidenceKind(item["kind"]); item["confidence"]=Confidence(item["confidence"]); item["timestamp"]=datetime.fromisoformat(item["timestamp"]); evidence=Evidence(**item); self._items[evidence.evidence_id]=evidence
    def add(self, evidence: Evidence) -> Evidence:
        self._items[evidence.evidence_id]=evidence
        if self.db:
            data=asdict(evidence); data["kind"]=evidence.kind.value; data["confidence"]=evidence.confidence.value; data["timestamp"]=evidence.timestamp.isoformat(); self.db.execute("INSERT OR REPLACE INTO evidence VALUES (?,?)",(evidence.evidence_id,json.dumps(data,sort_keys=True))); self.db.commit()
        return evidence
    def get(self, evidence_id: str) -> Evidence: return self._items[evidence_id]
    def for_claim(self, claim: str) -> tuple[Evidence, ...]: return tuple(item for item in self._items.values() if item.claim == claim)
    def close(self) -> None:
        if self.db: self.db.close()
class ConflictResolution(str, Enum): CONSENSUS="consensus"; VERIFY="verify"; ESCALATE="escalate"
@dataclass(frozen=True, slots=True)
class ConflictDecision:
    resolution: ConflictResolution; claim: str; evidence: tuple[Evidence, ...]; reason: str
class ConflictResolver:
    def resolve(self, claim: str, messages: tuple[AgentMessage, ...], store: EvidenceStore, *, high_risk: bool = False) -> ConflictDecision:
        evidence=tuple(store.get(identifier) for message in messages for identifier in message.evidence_ids); values={m.payload.get("value") for m in messages if m.payload.get("value")}
        if len(values)<=1 and evidence: return ConflictDecision(ConflictResolution.CONSENSUS,claim,evidence,"agents agree with evidence")
        return ConflictDecision(ConflictResolution.ESCALATE if high_risk else ConflictResolution.VERIFY,claim,evidence,"conflicting claims require independent verification")
