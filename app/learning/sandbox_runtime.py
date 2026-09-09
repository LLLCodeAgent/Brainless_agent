"""Disposable local sandbox construction for candidate-skill runners."""
from __future__ import annotations
import tempfile
from dataclasses import dataclass
from pathlib import Path
from app.agents.manager import AgentManager
from app.autonomy.controllers import FilesystemComputerController
from app.autonomy.executor import ActionRuntime

@dataclass(slots=True)
class DisposableFilesystemSandbox:
    """Owns a temporary filesystem controller; callers must still use ActionRuntime."""
    directory: tempfile.TemporaryDirectory[str]
    manager: AgentManager
    runtime: ActionRuntime
    @property
    def root(self) -> Path: return Path(self.directory.name)
    def close(self) -> None: self.directory.cleanup()
    def __enter__(self) -> "DisposableFilesystemSandbox": return self
    def __exit__(self, *_: object) -> None: self.close()

def create_filesystem_sandbox() -> DisposableFilesystemSandbox:
    directory = tempfile.TemporaryDirectory(prefix="brainless-skill-")
    manager = AgentManager()
    return DisposableFilesystemSandbox(directory, manager, ActionRuntime(manager, FilesystemComputerController(Path(directory.name))))
