"""Validate a response copied by a provider's own visible Copy control."""
from __future__ import annotations

from collections.abc import Callable

from app.computer.clipboard import read_text
from app.extraction.response_extractor import validate_response


class ClipboardExtractor:
    def __init__(self, reader: Callable[[], str] = read_text) -> None:
        self._reader = reader

    def extract(self) -> str:
        return validate_response(self._reader())
