"""Capability permissions and policy decisions for agent-owned tool access."""
from __future__ import annotations

from enum import Enum


class Permission(str, Enum):
    KEYBOARD_READ = "keyboard.read"
    KEYBOARD_WRITE = "keyboard.write"
    MOUSE_READ = "mouse.read"
    MOUSE_MOVE = "mouse.move"
    MOUSE_CLICK = "mouse.click"
    MOUSE_DRAG = "mouse.drag"
    SCREEN_READ = "screen.read"
    WINDOW_READ = "window.read"
    WINDOW_CONTROL = "window.control"
    CLIPBOARD_READ = "clipboard.read"
    CLIPBOARD_WRITE = "clipboard.write"
    BROWSER_READ = "browser.read"
    BROWSER_NAVIGATE = "browser.navigate"
    BROWSER_CLICK = "browser.click"
    BROWSER_TYPE = "browser.type"
    FILESYSTEM_READ = "filesystem.read"
    FILESYSTEM_WRITE = "filesystem.write"
    PROCESS_READ = "process.read"
    PROCESS_EXECUTE = "process.execute"


COMPUTER_READ = frozenset({Permission.SCREEN_READ.value, Permission.MOUSE_READ.value, Permission.KEYBOARD_READ.value})
COMPUTER_CONTROL = frozenset({Permission.MOUSE_MOVE.value, Permission.MOUSE_CLICK.value, Permission.KEYBOARD_WRITE.value})
BROWSER = frozenset({Permission.BROWSER_READ.value, Permission.BROWSER_NAVIGATE.value,
                     Permission.BROWSER_CLICK.value, Permission.BROWSER_TYPE.value})
FILESYSTEM = frozenset({Permission.FILESYSTEM_READ.value, Permission.FILESYSTEM_WRITE.value})
PROCESS = frozenset({Permission.PROCESS_READ.value, Permission.PROCESS_EXECUTE.value})


class ApprovalMode(str, Enum):
    AUTO_APPROVE = "auto_approve"
    REQUIRE_APPROVAL = "require_approval"
    DENY = "deny"


class PermissionDenied(PermissionError):
    def __init__(self, agent_id: str, permission: str, reason: str) -> None:
        self.agent_id, self.permission, self.reason = agent_id, permission, reason
        super().__init__(f"PERMISSION_DENIED {permission}: {reason}")


class ApprovalRequired(PermissionDenied):
    pass


class PermissionPolicy:
    """Global policy layer; ownership checks remain in the agent manager."""
    def __init__(self, modes: dict[str, ApprovalMode] | None = None) -> None:
        self.modes = modes or {}
        self._approved: set[tuple[str, str]] = set()

    def approve_once(self, agent_id: str, permission: str) -> None:
        """Runtime-only one-shot approval consumed by the next policy check."""
        self._approved.add((agent_id, permission))

    def check(self, agent_id: str, permission: str) -> None:
        mode = self.modes.get(permission, ApprovalMode.AUTO_APPROVE)
        if mode is ApprovalMode.DENY:
            raise PermissionDenied(agent_id, permission, "Global policy denies this permission")
        if mode is ApprovalMode.REQUIRE_APPROVAL:
            if (agent_id, permission) in self._approved:
                self._approved.remove((agent_id, permission))
                return
            raise ApprovalRequired(agent_id, permission, "Human approval is required")
