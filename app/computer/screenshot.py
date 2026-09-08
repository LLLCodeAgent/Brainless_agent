"""Screenshot capture for observable recovery evidence."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import Page


class ScreenshotRecorder:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    async def capture(self, page: Page, label: str) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = self.directory / f"{timestamp}-{label}.png"
        await page.screenshot(path=str(path), full_page=False)
        return path
