"""Provider registry keeps the runtime independent of website adapters."""
from __future__ import annotations

from app.config.settings import ProviderSettings
from app.providers.base_provider import ChatbotProvider
from app.providers.chatgpt import ChatGPTProvider
from app.providers.claude import ClaudeProvider
from app.providers.gemini import GeminiProvider
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.browser.browser_manager import BrowserManager


class ProviderRegistry:
    def __init__(self, providers: dict[str, ChatbotProvider]) -> None:
        self._providers = providers

    @classmethod
    def from_settings(cls, browser: BrowserManager, settings: dict[str, ProviderSettings]) -> "ProviderRegistry":
        classes = {"chatgpt": ChatGPTProvider, "gemini": GeminiProvider, "claude": ClaudeProvider}
        return cls({name: classes[name](browser, config.url) for name, config in settings.items()
                    if config.enabled and name in classes})

    def get(self, name: str) -> ChatbotProvider:
        try:
            return self._providers[name]
        except KeyError as error:
            raise KeyError(f"Unknown or disabled provider: {name}") from error

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._providers)
