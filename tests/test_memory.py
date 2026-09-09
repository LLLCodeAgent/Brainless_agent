from datetime import datetime, timezone

from app.memory.models import MemoryRecord
from app.memory.sqlite_memory import SQLiteMemory


def test_sqlite_memory_stores_and_searches(tmp_path) -> None:
    memory = SQLiteMemory(tmp_path / "memory.db")
    memory.store(MemoryRecord("task-1", datetime.now(timezone.utc), "chatgpt", "browser automation",
                              "Use semantic locators", "completed", 1.2, "single_provider", True))
    results = memory.search("semantic")
    memory.close()
    assert len(results) == 1
    assert results[0].provider == "chatgpt"
