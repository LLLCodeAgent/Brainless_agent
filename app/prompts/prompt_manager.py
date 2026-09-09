from pathlib import Path

from app.prompts.template_engine import render_template


class PromptManager:
    def __init__(self, prompt_root: Path) -> None:
        self.prompt_root = prompt_root

    def render(self, profile: str, **variables: str) -> str:
        provider = variables.get("provider")
        provider_path = self.prompt_root / profile / f"{provider}.txt" if provider else None
        template_path = provider_path if provider_path and provider_path.is_file() else self.prompt_root / profile / "default.txt"
        template = template_path.read_text(encoding="utf-8")
        return render_template(template, variables)
