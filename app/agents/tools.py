"""Central registry that is the only supported path to agent tool execution."""
from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


ToolHandler = Callable[[dict[str, Any]], Awaitable[Any] | Any]


@dataclass(frozen=True, slots=True)
class ToolSpec:
    tool_id: str
    name: str
    description: str
    required_permissions: frozenset[str]
    risk: RiskLevel
    handler: ToolHandler
    input_schema: tuple[str, ...] = ()
    output_schema: str = "any"
    category: str = "general"
    supported_platforms: tuple[str, ...] = ("any",)
    reversible: bool = True
    destructive: bool = False


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, tool: ToolSpec) -> None:
        if tool.tool_id in self._tools:
            raise ValueError(f"Tool already registered: {tool.tool_id}")
        self._tools[tool.tool_id] = tool

    def get(self, tool_id: str) -> ToolSpec:
        try:
            return self._tools[tool_id]
        except KeyError as error:
            raise KeyError(f"Unknown tool: {tool_id}") from error

    def contains(self, tool_id: str) -> bool:
        return tool_id in self._tools

    @property
    def tool_ids(self) -> tuple[str, ...]:
        return tuple(self._tools)

    async def invoke(self, tool_id: str, arguments: dict[str, Any]) -> Any:
        tool = self.get(tool_id)
        if not isinstance(arguments, dict):
            raise TypeError("Tool arguments must be an object")
        missing = set(tool.input_schema) - set(arguments)
        if missing:
            raise ValueError(f"Missing tool arguments: {', '.join(sorted(missing))}")
        result = tool.handler(arguments)
        return await result if inspect.isawaitable(result) else result
