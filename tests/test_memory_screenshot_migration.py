from datetime import datetime, timezone
import sqlite3

from app.memory.models import MemoryRecord
from app.memory.sqlite_memory import SQLiteMemory


def test_sqlite_memory_migrates_and_stores_screenshot_path(tmp_path) -> None:
    database = tmp_path / "legacy.db"
    connection = sqlite3.connect(database)
    connection.execute("""CREATE TABLE task_results (
        id INTEGER PRIMARY KEY, task_id TEXT NOT NULL, timestamp TEXT NOT NULL,
        provider TEXT NOT NULL, prompt TEXT NOT NULL, response TEXT NOT NULL,
        status TEXT NOT NULL, duration_seconds REAL NOT NULL, workflow TEXT NOT NULL,
        final_result INTEGER NOT NULL, error TEXT)""")
    connection.close()
    memory = SQLiteMemory(database)
    memory.store(MemoryRecord("task", datetime.now(timezone.utc), "chatgpt", "prompt", "response",
                              "completed", 1.0, "single", screenshot_path="screenshots/result.png"))
    records = memory.search("response")
    memory.close()
    assert records[0].screenshot_path == "screenshots/result.png"
