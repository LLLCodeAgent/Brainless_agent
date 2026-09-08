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
