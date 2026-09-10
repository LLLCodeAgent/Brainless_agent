"""Production tool adapters registered behind AgentManager permission checks."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from app.agents.tools import RiskLevel, ToolRegistry, ToolSpec
from app.browser.browser_manager import BrowserManager
from app.computer.keyboard import Keyboard
from app.computer.mouse import Mouse
from app.computer.screenshot import ScreenshotRecorder
from app.safety.permissions import Permission


def register_runtime_tools(registry: ToolRegistry, browser: BrowserManager, repository_root: Path,
                           keyboard: Keyboard | None = None, mouse: Mouse | None = None,
                           screenshots: ScreenshotRecorder | None = None) -> None:
    """Register real adapters; callers must invoke them through AgentManager."""
    async def browser_title(arguments: dict[str, Any]) -> str:
        page = await browser.page_for(str(arguments["url"]))
        return await page.title()

    async def browser_type(arguments: dict[str, Any]) -> str:
        page = await browser.page_for(str(arguments["url"]))
        await page.locator(str(arguments["selector"])).fill(str(arguments["text"]))
        return "typed"

    def type_keys(arguments: dict[str, Any]) -> str:
        (keyboard or Keyboard()).type_text(str(arguments["text"]))
        return "typed"

    def click_mouse(arguments: dict[str, Any]) -> str:
        (mouse or Mouse()).click(int(arguments["x"]), int(arguments["y"]))
        return "clicked"

    def write_file(arguments: dict[str, Any]) -> str:
        path = (repository_root / str(arguments["path"])).resolve()
        if repository_root.resolve() not in path.parents:
            raise ValueError("Filesystem writes must remain inside the repository")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(arguments["content"]), encoding="utf-8")
        return str(path)

    async def execute_process(arguments: dict[str, Any]) -> dict[str, object]:
        command = arguments["command"]
        if not isinstance(command, list) or not command or not all(isinstance(item, str) for item in command):
            raise ValueError("command must be a non-empty list of strings")
        process = await asyncio.create_subprocess_exec(*command, cwd=str(repository_root),
                                                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await process.communicate()
        return {"returncode": process.returncode, "stdout": stdout.decode(), "stderr": stderr.decode()}

    async def screenshot(arguments: dict[str, Any]) -> str:
        if screenshots is None:
            raise RuntimeError("Screenshot recorder is not configured")
        page = await browser.page_for(str(arguments["url"]))
        return str(await screenshots.capture(page, str(arguments["label"])))

    registry.register(ToolSpec("browser.read_title", "Read browser title", "Open a page and read its title",
                               frozenset({Permission.BROWSER_READ.value, Permission.BROWSER_NAVIGATE.value}), RiskLevel.LOW,
                               browser_title, ("url",), "string"))
    registry.register(ToolSpec("browser.type", "Type in browser", "Fill a verified DOM field",
                               frozenset({Permission.BROWSER_NAVIGATE.value, Permission.BROWSER_TYPE.value}), RiskLevel.MEDIUM,
                               browser_type, ("url", "selector", "text"), "string"))
    registry.register(ToolSpec("keyboard.write", "Type keys", "Type through the OS keyboard", frozenset({Permission.KEYBOARD_WRITE.value}),
                               RiskLevel.HIGH, type_keys, ("text",), "string"))
    registry.register(ToolSpec("mouse.click", "Click mouse", "Click through the OS mouse", frozenset({Permission.MOUSE_CLICK.value}),
                               RiskLevel.HIGH, click_mouse, ("x", "y"), "string"))
    registry.register(ToolSpec("filesystem.write", "Write repository file", "Write a UTF-8 file inside the repository",
                               frozenset({Permission.FILESYSTEM_WRITE.value}), RiskLevel.HIGH, write_file,
                               ("path", "content"), "path"))
    registry.register(ToolSpec("process.execute", "Execute process", "Run an explicit command in the repository",
                               frozenset({Permission.PROCESS_EXECUTE.value}), RiskLevel.HIGH, execute_process,
                               ("command",), "process result"))
    registry.register(ToolSpec("screen.capture", "Capture browser screenshot", "Capture evidence from a browser page",
                               frozenset({Permission.SCREEN_READ.value, Permission.BROWSER_NAVIGATE.value}), RiskLevel.MEDIUM,
                               screenshot, ("url", "label"), "path"))
