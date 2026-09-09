"""Confidence-scored semantic target resolution with deterministic fallbacks."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol

from app.autonomy.models import ComputerState


@dataclass(frozen=True, slots=True)
class ResolvedTarget:
    target: str
    method: str
    confidence: float
    evidence: str
    coordinates: tuple[int, int] | None = None


class TargetProvider(Protocol):
    def resolve(self, query: str, state: ComputerState) -> ResolvedTarget | None: ...


class TargetResolver:
    def __init__(self, providers: tuple[TargetProvider, ...] = (), confidence_threshold: float = .75) -> None:
        self.providers, self.confidence_threshold = providers, confidence_threshold

    def resolve(self, query: str, state: ComputerState, *, coordinate_fallback: tuple[int, int] | None = None) -> ResolvedTarget | None:
        candidates = [candidate for provider in self.providers if (candidate := provider.resolve(query, state))]
        # Text matching is a safe generic provider from the current observed UI.
        lowered = query.casefold()
        for text in state.visible_ui:
            if lowered in text.casefold():
                candidates.append(ResolvedTarget(query, "text", .8, text))
        if coordinate_fallback:
            candidates.append(ResolvedTarget(query, "coordinates", .2, "explicit fallback", coordinate_fallback))
        eligible = [item for item in candidates if item.confidence >= self.confidence_threshold]
        return max(eligible, key=lambda item: item.confidence, default=None)
