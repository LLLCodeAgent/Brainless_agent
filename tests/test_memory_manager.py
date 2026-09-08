from datetime import datetime, timezone

from app.memory.memory_manager import MemoryManager
from app.memory.models import MemoryRecord
from app.memory.sqlite_memory import SQLiteMemory


def test_memory_manager_formats_bounded_relevant_context(tmp_path) -> None:
    storage = SQLiteMemory(tmp_path / "memory.db")
    storage.store(MemoryRecord("one", datetime.now(timezone.utc), "chatgpt", "browser automation",
                               "Semantic locators are robust.", "completed", 1.0, "single"))
    storage.store(MemoryRecord("two", datetime.now(timezone.utc), "chatgpt", "other", "Not selected",
                               "failed", 1.0, "single"))
    context = MemoryManager(storage, max_characters=100).relevant_context("browser patterns")
    storage.close()
    assert "Semantic locators" in context
    assert "Not selected" not in context
