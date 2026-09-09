"""SQLite-backed, local-only task result storage."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from app.memory.models import MemoryRecord


class SQLiteMemory:
    def __init__(self, database_path: Path) -> None:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(database_path)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("""CREATE TABLE IF NOT EXISTS task_results (
            id INTEGER PRIMARY KEY, task_id TEXT NOT NULL, timestamp TEXT NOT NULL,
            provider TEXT NOT NULL, prompt TEXT NOT NULL, response TEXT NOT NULL,
            status TEXT NOT NULL, duration_seconds REAL NOT NULL, workflow TEXT NOT NULL,
            final_result INTEGER NOT NULL, error TEXT, screenshot_path TEXT)""")
        columns = {row[1] for row in self._connection.execute("PRAGMA table_info(task_results)")}
        if "screenshot_path" not in columns:
            self._connection.execute("ALTER TABLE task_results ADD COLUMN screenshot_path TEXT")
        self._connection.commit()

    def store(self, record: MemoryRecord) -> None:
        self._connection.execute("""INSERT INTO task_results
            (task_id,timestamp,provider,prompt,response,status,duration_seconds,workflow,final_result,error,screenshot_path)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (record.task_id, record.timestamp.isoformat(), record.provider,
            record.prompt, record.response, record.status, record.duration_seconds, record.workflow,
            int(record.final_result), record.error, record.screenshot_path))
        self._connection.commit()

    def search(self, query: str, limit: int = 5) -> list[MemoryRecord]:
        terms = [term for term in query.split() if len(term) >= 3] or [query]
        conditions = " OR ".join("response LIKE ? OR prompt LIKE ?" for _ in terms)
        values = [value for term in terms for value in (f"%{term}%", f"%{term}%")]
        rows = self._connection.execute(f"SELECT * FROM task_results WHERE {conditions} "
            "ORDER BY timestamp DESC LIMIT ?", (*values, limit)).fetchall()
        from datetime import datetime
        return [MemoryRecord(row["task_id"], datetime.fromisoformat(row["timestamp"]), row["provider"],
                row["prompt"], row["response"], row["status"], row["duration_seconds"], row["workflow"],
                bool(row["final_result"]), row["error"], row["screenshot_path"]) for row in rows]

    def close(self) -> None:
        self._connection.close()
