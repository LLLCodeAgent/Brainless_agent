"""Deterministic task classification and provider selection.

This module deliberately performs only local, explainable parsing. A selected
provider should never be enabled by a substring in unrelated text.
"""
import re

from app.tasks.task import Task


def parse_task(objective: str, available_providers: tuple[str, ...]) -> Task:
    if not available_providers:
        raise ValueError("At least one provider must be available")
    text = objective.lower()
    category = _classify_category(text)
    mentioned = [name for name in available_providers if re.search(rf"\b{re.escape(name)}\b", text)]
    multi = len(mentioned) > 1 or ("compare" in text and len(available_providers) > 1)
    providers = mentioned or (["chatgpt"] if "chatgpt" in available_providers else [available_providers[0]])
    if multi:
        providers = mentioned or list(available_providers)
    synthesis_provider = "chatgpt" if "chatgpt" in providers else providers[0]
    return Task(objective=objective, category=category, providers=providers,
                strategy="multi_provider" if multi else "single_provider", synthesis=multi,
                synthesis_provider=synthesis_provider if multi else None)


def _classify_category(text: str) -> str:
    """Choose a prompt profile using explicit, stable keyword groups."""
    if any(word in text for word in ("code", "debug", "python", "implement", "refactor", "test")):
        return "coding"
    if any(word in text for word in ("analyze", "analyse", "analysis", "evaluate", "audit", "assess")):
        return "analysis"
    return "research"
