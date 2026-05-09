"""Tool abstract base class — modeled after claude-code-ts src/Tool.ts Tool interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """Result returned by tool execution."""
    content: str
    is_error: bool = False


@dataclass
class ToolContext:
    """Execution context passed to every tool call (like ToolUseContext in claude-code-ts)."""
    workspace_id: str
    conversation_id: str
    working_dir: str  # workspace file storage path


class Tool(ABC):
    """Unified tool interface. All tools (built-in, skill-based, future MCP) implement this."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name. LLM calls the tool by this name."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description for LLM to understand when to use this tool."""
        ...

    @property
    @abstractmethod
    def input_schema(self) -> dict:
        """JSON Schema describing the tool's input parameters."""
        ...

    @abstractmethod
    async def execute(self, input: dict, context: ToolContext) -> ToolResult:
        """Execute the tool with given input and context."""
        ...

    def to_openai_tool(self) -> dict:
        """Convert to OpenAI tool definition format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }

    def __repr__(self) -> str:
        return f"Tool(name='{self.name}')"
