from app.providers.base_provider import ChatbotProvider, ProviderSelectors


class GeminiProvider(ChatbotProvider):
    name = "gemini"

    def __init__(self, browser, url: str) -> None:
        super().__init__(browser, url, ProviderSelectors(
            input=("rich-textarea textarea", "textarea[aria-label*='Enter a prompt']", "div[contenteditable='true']"),
            response=("message-content", ".model-response-text"),
            stop=("button[aria-label*='Stop']",),
            copy=("button[aria-label*='Copy']",),
        ))
