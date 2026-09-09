"""Durable, contextual agent performance records used only as assignment advice."""
from __future__ import annotations
import sqlite3
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True, slots=True)
class AgentPerformance:
    agent_id: str; task_type: str; environment: str; successes: int; failures: int; verified: int; duration_ms: float; resource_cost: float
    @property
    def success_rate(self) -> float: return self.successes / (self.successes + self.failures) if self.successes + self.failures else 0.0

class AgentPerformanceMemory:
    def __init__(self, path: Path) -> None:
        self.db=sqlite3.connect(path); self.db.row_factory=sqlite3.Row
        self.db.execute("CREATE TABLE IF NOT EXISTS agent_performance(agent_id TEXT,task_type TEXT,environment TEXT,successes INTEGER,failures INTEGER,verified INTEGER,duration_ms REAL,resource_cost REAL,PRIMARY KEY(agent_id,task_type,environment))"); self.db.commit()
    def record(self, agent_id: str, task_type: str, environment: str, *, success: bool, verified: bool, duration_ms: float, resource_cost: float=0.0) -> None:
        row=self.db.execute("SELECT * FROM agent_performance WHERE agent_id=? AND task_type=? AND environment=?",(agent_id,task_type,environment)).fetchone()
        values=(int(success)+(row["successes"] if row else 0),int(not success)+(row["failures"] if row else 0),int(verified)+(row["verified"] if row else 0),duration_ms+(row["duration_ms"] if row else 0),resource_cost+(row["resource_cost"] if row else 0))
        self.db.execute("INSERT OR REPLACE INTO agent_performance VALUES (?,?,?,?,?,?,?,?)",(agent_id,task_type,environment,*values));self.db.commit()
    def best(self, task_type: str, environment: str) -> tuple[AgentPerformance,...]:
        return tuple(AgentPerformance(**dict(row)) for row in self.db.execute("SELECT * FROM agent_performance WHERE task_type=? AND environment=? ORDER BY CAST(successes AS REAL)/(successes+failures) DESC, duration_ms ASC",(task_type,environment)))
    def close(self)->None:self.db.close()
