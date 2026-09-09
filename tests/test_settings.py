from app.config.settings import load_settings


def test_default_settings_load() -> None:
    settings = load_settings()
    assert settings.providers["chatgpt"].url == "https://chatgpt.com/"
    assert settings.agent.max_retries == 3
