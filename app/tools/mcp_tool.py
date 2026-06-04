"""MCP tool wrapper — adapts MCP server tools into the Tool interface."""

import logging
from typing import Callable, Awaitable
from app.tools.base import Tool, ToolResult, ToolContext

logger = logging.getLogger("mcp_tool")


class MCPToolWrapper(Tool):
    """Wraps an MCP server tool as a Tool instance.

    LLM sees this as a regular tool. On execute, delegates to MCP server via
    the provided call_tool callback.
    """

    def __init__(
        self,
        server_name: str,
        tool_name: str,
        tool_description: str,
        input_schema: dict,
        call_tool: Callable[[str, dict], Awaitable[ToolResult]],
    ):
        self._server_name = server_name
        self._tool_name = tool_name
        self._tool_description = tool_description
        self._input_schema = input_schema
        self._call_tool = call_tool

    @property
    def name(self) -> str:
        return f"mcp__{self._server_name}__{self._tool_name}"

    @property
    def description(self) -> str:
        return self._tool_description

    @property
    def input_schema(self) -> dict:
        """Return JSON Schema for tool input parameters."""
        schema = dict(self._input_schema) if self._input_schema else {}
        schema.setdefault("type", "object")
        # Ensure properties is a dict (some MCP servers omit it)
        if "properties" not in schema:
            schema["properties"] = {}
        return schema

    @property
    def server_name(self) -> str:
        return self._server_name

    @property
    def tool_name(self) -> str:
        return self._tool_name

    async def execute(self, input: dict, context: ToolContext) -> ToolResult:
        """Execute the MCP tool by calling back into the connection manager."""
        logger.debug(
            "Executing MCP tool mcp__%s__%s", self._server_name, self._tool_name
        )
        try:
            return await self._call_tool(self._tool_name, input)
        except Exception as e:
            logger.exception(
                "MCP tool mcp__%s__%s failed", self._server_name, self._tool_name
            )
            return ToolResult(
                content=f"MCP tool error: {e}", is_error=True
            )
