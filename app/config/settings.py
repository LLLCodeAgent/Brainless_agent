"""Typed, file-backed settings without secrets or provider API credentials."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class BrowserSettings(BaseModel):
    channel: str = "chrome"
    headless: bool = False
    profile_dir: Path = Path("data/browser-profile")
    navigation_timeout_seconds: int = Field(default=45, ge=1)


class AgentSettings(BaseModel):
    max_retries: int = Field(default=3, ge=0)
    max_actions: int = Field(default=100, ge=1)
    max_task_minutes: int = Field(default=30, ge=1)
    emergency_stop_hotkey: str = "CTRL+SHIFT+ESC"


class ProviderSettings(BaseModel):
    enabled: bool = True
    url: str


class PromptSettings(BaseModel):
    default_profile: str = "research"


class WorkflowSettings(BaseModel):
    multi_provider_synthesis: bool = True


class Settings(BaseModel):
    browser: BrowserSettings = BrowserSettings()
    agent: AgentSettings = AgentSettings()
    providers: dict[str, ProviderSettings]
    prompts: PromptSettings = PromptSettings()
    workflows: WorkflowSettings = WorkflowSettings()


def load_settings(path: Path | None = None) -> Settings:
    """Load settings relative to the repository root unless a path is supplied."""
    config_path = path or Path(__file__).with_name("providers.yaml")
    raw: dict[str, Any] = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return Settings.model_validate(raw)
