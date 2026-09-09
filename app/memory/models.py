from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    task_id: str
    timestamp: datetime
    provider: str
    prompt: str
    response: str
    status: str
    duration_seconds: float
    workflow: str
    final_result: bool = False
    error: str | None = None
    screenshot_path: str | None = None
