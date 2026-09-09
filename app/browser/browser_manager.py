"""Playwright-backed persistent Chrome session manager."""
from __future__ import annotations

import logging
from pathlib import Path

from playwright.async_api import BrowserContext, Page, Playwright, async_playwright

from app.config.settings import BrowserSettings

LOGGER = logging.getLogger(__name__)


class BrowserManager:
    """Owns one persistent user-visible browser context; it never handles credentials."""

    def __init__(self, settings: BrowserSettings, repository_root: Path) -> None:
        self._settings = settings
        self._repository_root = repository_root
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None

    async def start(self) -> None:
        if self._context:
            return
        profile_dir = self._settings.profile_dir
        if not profile_dir.is_absolute():
            profile_dir = self._repository_root / profile_dir
        profile_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = await async_playwright().start()
        try:
            self._context = await self._playwright.chromium.launch_persistent_context(
                str(profile_dir), channel=self._settings.channel,
                headless=self._settings.headless,
                viewport={"width": 1440, "height": 1000},
            )
        except Exception:
            await self._playwright.stop()
            self._playwright = None
            raise
        self._context.set_default_timeout(self._settings.navigation_timeout_seconds * 1000)
        LOGGER.info("Persistent Chrome session started: %s", profile_dir)

    async def page_for(self, url: str) -> Page:
        if not self._context:
            raise RuntimeError("BrowserManager.start() must be called first")
        page = next((page for page in self._context.pages if page.url.startswith(url)), None)
        if page is None:
            page = await self._context.new_page()
        await page.bring_to_front()
        if not page.url.startswith(url):
            await page.goto(url, wait_until="domcontentloaded")
        return page

    async def close(self) -> None:
        if self._context:
            await self._context.close()
            self._context = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        LOGGER.info("Browser session closed")
