from app.providers.base_provider import ChatbotProvider, ProviderSelectors


class ClaudeProvider(ChatbotProvider):
    name = "claude"

    def __init__(self, browser, url: str) -> None:
        super().__init__(browser, url, ProviderSelectors(
            input=("div[contenteditable='true'][role='textbox']", "textarea[placeholder*='Message']"),
            response=("[data-is-streaming='false']", "div.font-claude-response"),
            stop=("button[aria-label*='Stop']",),
            copy=("button[aria-label*='Copy']",),
        ))
