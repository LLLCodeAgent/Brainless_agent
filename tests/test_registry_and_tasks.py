from app.providers.registry import ProviderRegistry
from app.tasks.task_parser import parse_task


def test_registry_reports_configured_provider_names() -> None:
    registry = ProviderRegistry({})
    assert registry.names == ()


def test_task_parser_detects_multi_provider_request() -> None:
    task = parse_task("Research and compare chatgpt and gemini", ("chatgpt", "gemini", "claude"))
    assert task.providers == ["chatgpt", "gemini"]
    assert task.synthesis is True
    assert task.synthesis_provider == "chatgpt"


def test_task_parser_selects_analysis_profile_and_avoids_provider_substrings() -> None:
    task = parse_task("Analyze Claude's approach, not myclaude-copy", ("claude", "gemini"))
    assert task.category == "analysis"
    assert task.providers == ["claude"]
