"""Safe, bounded retrieval of local task context for prompt rendering."""
from __future__ import annotations

from app.memory.sqlite_memory import SQLiteMemory


class MemoryManager:
    def __init__(self, storage: SQLiteMemory, max_records: int = 3, max_characters: int = 6_000) -> None:
        self.storage = storage
        self.max_records = max_records
        self.max_characters = max_characters

    def relevant_context(self, query: str) -> str:
        records = self.storage.search(query, limit=self.max_records)
        blocks = [f"Previous {record.provider} result ({record.timestamp.isoformat()}):\n{record.response}"
                  for record in records if record.status == "completed" and record.response]
        return "\n\n".join(blocks)[:self.max_characters]
