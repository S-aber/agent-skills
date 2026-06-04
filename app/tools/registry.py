"""Tool registry — modeled after claude-code-ts src/tools.ts getAllBaseTools()."""

from app.tools.base import Tool
from app.tools.read_file import ReadFileTool
from app.tools.write_file import WriteFileTool
from app.tools.execute_python import ExecutePythonTool
from app.tools.execute_bash import ExecuteBashTool
from app.tools.web_fetch import WebFetchTool
from app.tools.web_search import WebSearchTool


class ToolRegistry:
    """Manages available tools. Supports dynamic registration (e.g., skill-based tools)."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._load_builtin_tools()

    def _load_builtin_tools(self):
        for tool in get_builtin_tools():
            self._tools[tool.name] = tool

    def register(self, tool: Tool):
        """Register a tool (e.g., a skill registered as a tool)."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def get_all(self) -> list[Tool]:
        return list(self._tools.values())

    def clear_dynamic(self):
        """Remove dynamically registered tools (skills + mcp), keep built-ins."""
        builtin_names = {t.name for t in get_builtin_tools()}
        self._tools = {k: v for k, v in self._tools.items() if k in builtin_names}

    def clear_mcp(self):
        """Remove MCP tools only (names starting with 'mcp__')."""
        self._tools = {k: v for k, v in self._tools.items() if not k.startswith("mcp__")}


def get_builtin_tools() -> list[Tool]:
    """Return all built-in tools. Like claude-code-ts getAllBaseTools()."""
    return [
        ReadFileTool(),
        WriteFileTool(),
        ExecutePythonTool(),
        ExecuteBashTool(),
        WebFetchTool(),
        WebSearchTool(),
    ]


def get_all_tools() -> list[Tool]:
    """Get all available tools (built-in only, no dynamic skills)."""
    return get_builtin_tools()
