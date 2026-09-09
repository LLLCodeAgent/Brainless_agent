import pytest

from app.runtime.task_manager import TaskManager


def test_task_manager_applies_selected_multi_provider_workflow() -> None:
    task = TaskManager(("chatgpt", "gemini", "claude")).create(
        "Compare approaches", ["gemini", "claude"], strategy="multi", prompt_profile="analysis"
    )
    assert task.providers == ["gemini", "claude"]
    assert task.synthesis is True
    assert task.synthesis_provider == "gemini"
    assert task.prompt_profile == "analysis"


def test_task_manager_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="Unknown"):
        TaskManager(("chatgpt",)).create("Task", ["claude"])


def test_task_manager_automatically_synthesizes_explicitly_selected_providers() -> None:
    task = TaskManager(("chatgpt", "gemini", "claude")).create(
        "Research browser automation", ["gemini", "claude"]
    )
    assert task.strategy == "multi_provider"
    assert task.synthesis is True
    assert task.synthesis_provider == "gemini"


def test_task_manager_rejects_invalid_multi_provider_selection() -> None:
    with pytest.raises(ValueError, match="at least two"):
        TaskManager(("chatgpt",)).create("Task", ["chatgpt"], strategy="multi")


def test_task_manager_rejects_duplicate_providers() -> None:
    with pytest.raises(ValueError, match="at most once"):
        TaskManager(("chatgpt", "gemini")).create("Task", ["chatgpt", "chatgpt"])
