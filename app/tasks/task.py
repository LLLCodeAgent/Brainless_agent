from dataclasses import dataclass, field
from uuid import uuid4


@dataclass(slots=True)
class Task:
    objective: str
    category: str = "research"
    providers: list[str] = field(default_factory=lambda: ["chatgpt"])
    strategy: str = "single_provider"
    prompt_profile: str | None = None
    synthesis: bool = False
    synthesis_provider: str | None = None
    id: str = field(default_factory=lambda: str(uuid4()))
