"""Application composition root shared by CLI and desktop UI."""
from __future__ import annotations

from pathlib import Path

from app.browser.browser_manager import BrowserManager
from app.agents.manager import AgentManager
from app.agents.runtime_tools import register_runtime_tools
from app.agents.tools import ToolRegistry
from app.computer.screenshot import ScreenshotRecorder
from app.config.settings import Settings
from app.memory.sqlite_memory import SQLiteMemory
from app.prompts.prompt_manager import PromptManager
from app.providers.registry import ProviderRegistry
from app.runtime.agent_runtime import AgentRuntime
from app.autonomy.controllers import PlaywrightComputerController
from app.autonomy.executor import ActionRuntime as AutonomousActionRuntime
from app.autonomy.orchestrator import AutonomousRuntime
from app.safety.intervention import UserInterventionGate


class Application:
    def __init__(self, root: Path, settings: Settings, intervention: UserInterventionGate | None = None) -> None:
        self.memory = SQLiteMemory(root / "data/memory.db")
        self.browser = BrowserManager(settings.browser, root)
        tools = ToolRegistry()
        register_runtime_tools(tools, self.browser, root, screenshots=ScreenshotRecorder(root / "screenshots"))
        self.agent_manager = AgentManager(tools, audit_store=self.memory)
        self.autonomous_actions = AutonomousActionRuntime(
            self.agent_manager, PlaywrightComputerController(self.browser), audit_store=self.memory)
        self.autonomous = AutonomousRuntime(self.agent_manager, self.autonomous_actions)
        self.providers = ProviderRegistry.from_settings(self.browser, settings.providers)
        self.runtime = AgentRuntime(
            self.browser, self.providers, PromptManager(root / "prompts"), self.memory,
            settings.agent.max_retries, settings.agent.max_actions, settings.agent.max_task_minutes,
            screenshots=ScreenshotRecorder(root / "screenshots"),
            intervention=intervention,
        )

    async def close(self) -> None:
        self.memory.close()
        await self.browser.close()
