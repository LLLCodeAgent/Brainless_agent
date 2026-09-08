"""Page observation snapshots used to verify browser actions."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from playwright.async_api import Page


@dataclass(frozen=True, slots=True)
class Observation:
    screenshot_path: str | None
    visible_text: str
    page_url: str
    page_title: str
    detected_elements: tuple[str, ...]
    focused_element: str | None
    timestamp: datetime


async def observe_page(page: Page, screenshot_path: str | None = None) -> Observation:
    focused, elements = await page.evaluate("""() => {
        const element = document.activeElement;
        const focus = element ? `${element.tagName}[${element.getAttribute('aria-label') || ''}]` : null;
        const interactive = [...document.querySelectorAll('button, textarea, input, [contenteditable=true], [role=button], [role=textbox]')]
          .filter(node => node.offsetParent !== null)
          .slice(0, 80)
          .map(node => `${node.tagName}[${node.getAttribute('aria-label') || node.getAttribute('placeholder') || node.getAttribute('role') || ''}]`);
        return [focus, interactive];
    }""")
    return Observation(
        screenshot_path=screenshot_path,
        visible_text=(await page.locator("body").inner_text())[:20_000],
        page_url=page.url,
        page_title=await page.title(),
        detected_elements=tuple(elements),
        focused_element=focused,
        timestamp=datetime.now(timezone.utc),
    )
