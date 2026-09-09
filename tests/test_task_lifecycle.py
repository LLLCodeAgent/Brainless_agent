import asyncio
import time

import pytest

from app.memory.sqlite_memory import SQLiteMemory
from app.prompts.prompt_manager import PromptManager
from app.runtime.agent_runtime import AgentRuntime
from app.runtime.state_manager import RuntimeState
from app.tasks.task import Task


class FakeBrowser:
    async def start(self) -> None:
        return None


class FakeProvider:
    page = None

    def __init__(self) -> None:
        self.sent_prompts: list[str] = []
        self.focused = False

    async def open(self) -> None:
        return None

    async def verify_page(self) -> None:
        return None

    async def start_conversation(self) -> None:
        self.focused = True

    async def send_prompt(self, prompt: str) -> None:
        assert self.focused
        self.sent_prompts.append(prompt)

    async def wait_for_response(self) -> None:
        return None

    async def extract_response(self) -> str:
        return "A verified browser response"

    async def recover(self) -> None:
        return None


class RecoveringProvider(FakeProvider):
    def __init__(self) -> None:
        super().__init__()
        self.extraction_attempts = 0
        self.recovered = False

    async def extract_response(self) -> str:
        self.extraction_attempts += 1
        if self.extraction_attempts == 1:
            raise RuntimeError("temporary DOM failure")
        return "Recovered browser response"

    async def recover(self) -> None:
        self.recovered = True


class FakeRegistry:
    def __init__(self, provider: FakeProvider) -> None:
        self.provider = provider

    def get(self, name: str) -> FakeProvider:
        assert name == "chatgpt"
        return self.provider


def test_runtime_executes_and_persists_a_single_provider_task(tmp_path) -> None:
    async def scenario() -> None:
        memory = SQLiteMemory(tmp_path / "memory.db")
        provider = FakeProvider()
        runtime = AgentRuntime(
            FakeBrowser(), FakeRegistry(provider), PromptManager(tmp_path / "prompts"), memory, max_retries=0,
        )
        prompts = tmp_path / "prompts" / "research"
        prompts.mkdir(parents=True)
        (prompts / "default.txt").write_text("Task: {task}; provider: {provider}", encoding="utf-8")

        result = await runtime.run(Task("Investigate browser automation", providers=["chatgpt"]))

        assert "A verified browser response" in result
        assert provider.focused is True
        assert provider.sent_prompts == ["Task: Investigate browser automation; provider: chatgpt"]
        assert runtime.state.state is RuntimeState.COMPLETED
        assert RuntimeState.FOCUSING_INPUT in runtime.state.history
        records = memory.search("browser")
        assert len(records) == 1
        assert records[0].status == "completed"
        assert records[0].final_result is True
        memory.close()

    asyncio.run(scenario())


def test_runtime_cancels_an_action_when_the_global_task_budget_expires(tmp_path) -> None:
    async def scenario() -> None:
        memory = SQLiteMemory(tmp_path / "memory.db")
        runtime = AgentRuntime(FakeBrowser(), FakeRegistry(FakeProvider()), PromptManager(tmp_path), memory, max_retries=0)
        runtime.max_task_seconds = 0.01

        async def slow_operation() -> None:
            await asyncio.sleep(1)

        with pytest.raises(TimeoutError, match="Task exceeded"):
            await runtime._act("slow operation", slow_operation, time.monotonic())
        memory.close()

    asyncio.run(scenario())


def test_runtime_records_recovery_and_reobserves_before_retrying_extraction(tmp_path) -> None:
    async def scenario() -> None:
        memory = SQLiteMemory(tmp_path / "memory.db")
        provider = RecoveringProvider()
        runtime = AgentRuntime(FakeBrowser(), FakeRegistry(provider), PromptManager(tmp_path), memory, max_retries=1)
        runtime.state.transition(RuntimeState.EXTRACTING_RESPONSE)

        assert await runtime._extract_response("chatgpt", provider, time.monotonic()) == "Recovered browser response"
        assert provider.recovered is True
        assert provider.extraction_attempts == 2
        assert RuntimeState.RECOVERING in runtime.state.history
        assert runtime.actions.count == 2
        memory.close()

    asyncio.run(scenario())
