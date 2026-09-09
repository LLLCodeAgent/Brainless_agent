from pathlib import Path

from app.prompts.prompt_manager import PromptManager


def test_prompt_variables_render() -> None:
    rendered = PromptManager(Path("prompts")).render("research", task="Investigate", provider="chatgpt",
                                                       previous_results="", context="", requirements="")
    assert "Investigate" in rendered
    assert "chatgpt" in rendered


def test_provider_specific_template_overrides_default(tmp_path) -> None:
    profile = tmp_path / "research"
    profile.mkdir()
    (profile / "default.txt").write_text("default {task}", encoding="utf-8")
    (profile / "chatgpt.txt").write_text("provider {task}", encoding="utf-8")
    assert PromptManager(tmp_path).render("research", task="task", provider="chatgpt") == "provider task"
