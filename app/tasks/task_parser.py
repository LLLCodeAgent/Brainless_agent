"""Deterministic task classification; no reasoning API is used."""
from app.tasks.task import Task


def parse_task(objective: str, available_providers: tuple[str, ...]) -> Task:
    text = objective.lower()
    category = "coding" if any(word in text for word in ("code", "debug", "python", "implement")) else "research"
    mentioned = [name for name in available_providers if name in text]
    multi = len(mentioned) > 1 or ("compare" in text and len(available_providers) > 1)
    providers = mentioned or (["chatgpt"] if "chatgpt" in available_providers else [available_providers[0]])
    if multi:
        providers = mentioned or list(available_providers)
    synthesis_provider = "chatgpt" if "chatgpt" in providers else providers[0]
    return Task(objective=objective, category=category, providers=providers,
                strategy="multi_provider" if multi else "single_provider", synthesis=multi,
                synthesis_provider=synthesis_provider if multi else None)
