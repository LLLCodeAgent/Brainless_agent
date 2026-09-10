"""Minimal, redacted voice metadata persistence; raw audio is never accepted."""
from __future__ import annotations
import json
from pathlib import Path
from threading import RLock
from typing import Any


class VoiceMetadataStore:
    def __init__(self, path: Path, retention: int = 200) -> None:
        self.path, self.retention, self._lock = path, retention, RLock()

    def append(self, record: dict[str, Any], *, include_transcript: bool = False) -> None:
        safe = {key: value for key, value in record.items() if key != "audio"}
        if not include_transcript: safe.pop("transcript", None)
        safe = _redact(safe)
        with self._lock:
            records = list(self.all())[-self.retention + 1:]
            records.append(safe); self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(records, sort_keys=True), encoding="utf-8"); temporary.replace(self.path)

    def all(self) -> tuple[dict[str, Any], ...]:
        with self._lock:
            return tuple(json.loads(self.path.read_text(encoding="utf-8"))) if self.path.exists() else ()


def _redact(value):
    sensitive = ("password", "secret", "token", "api key", "api_key", "credential", "cookie")
    if isinstance(value, str) and any(term in value.casefold() for term in sensitive): return "[REDACTED]"
    if isinstance(value, dict): return {key: _redact(item) for key, item in value.items()}
    if isinstance(value, list): return [_redact(item) for item in value]
    return value
