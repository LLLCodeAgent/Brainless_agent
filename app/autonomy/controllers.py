"""Replaceable computer-control interfaces; no agent receives backend access."""
from __future__ import annotations

from typing import Any, Protocol
from pathlib import Path

from app.autonomy.models import ComputerState, RuntimeErrorDetail, ErrorCode


class ComputerController(Protocol):
    async def observe(self) -> ComputerState: ...
    async def execute(self, action_type: str, arguments: dict[str, Any]) -> Any: ...


class BrowserController(Protocol):
    async def navigate(self, url: str) -> str: ...


class FilesystemController(Protocol):
    async def read(self, path: str) -> str: ...
    async def write(self, path: str, content: str) -> str: ...
    async def exists(self, path: str) -> bool: ...


class FilesystemComputerController:
    """Real, repository-scoped filesystem controller for autonomous tasks."""
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _path(self, value: str) -> Path:
        path = (self.root / value).resolve()
        if path != self.root and self.root not in path.parents:
            raise ValueError("Filesystem action escapes the configured root")
        return path

    async def observe(self) -> ComputerState:
        return ComputerState(active_application="filesystem", visible_ui=tuple(
            str(path.relative_to(self.root)) for path in self.root.iterdir()))

    async def execute(self, action_type: str, arguments: dict[str, Any]) -> Any:
        path = self._path(str(arguments.get("path", "")))
        if action_type == "filesystem.write":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(str(arguments["content"]), encoding="utf-8")
            return str(path)
        if action_type == "filesystem.read":
            return path.read_text(encoding="utf-8")
        if action_type == "filesystem.exists":
            return path.exists()
        raise RuntimeErrorDetail(ErrorCode.CAPABILITY_UNAVAILABLE,
                                 f"{action_type} is not available from this controller")


class PlaywrightComputerController:
    """Real browser-backed controller. Unsupported OS actions fail explicitly."""
    def __init__(self, browser) -> None:
        self.browser = browser
        self._url: str | None = None

    async def observe(self) -> ComputerState:
        if not self._url:
            return ComputerState(active_application="browser")
        page = await self.browser.page_for(self._url)
        return ComputerState(active_application="browser", active_window=await page.title(),
                             browser_url=page.url, browser_title=await page.title(),
                             visible_ui=tuple((await page.locator("body").inner_text())[:2000].splitlines()[:80]))

    async def execute(self, action_type: str, arguments: dict[str, Any]) -> Any:
        if action_type == "browser.navigate":
            self._url = str(arguments["url"])
            page = await self.browser.page_for(self._url)
            return {"url": page.url, "title": await page.title()}
        raise RuntimeErrorDetail(ErrorCode.CAPABILITY_UNAVAILABLE,
                                 f"{action_type} is not available from this controller")
