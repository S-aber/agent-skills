import os
from app.tools.base import Tool, ToolResult, ToolContext


class ReadFileTool(Tool):
    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Read a file from the workspace. Supports reading specific line ranges."

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to read, relative to workspace root.",
                },
                "offset": {
                    "type": "integer",
                    "description": "Line number to start reading from (0-indexed).",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of lines to read.",
                },
            },
            "required": ["file_path"],
        }

    async def execute(self, input: dict, context: ToolContext) -> ToolResult:
        file_path = input["file_path"]
        full_path = os.path.join(context.working_dir, file_path)

        # Security: prevent path traversal
        real_path = os.path.realpath(full_path)
        real_workspace = os.path.realpath(context.working_dir)
        if not real_path.startswith(real_workspace):
            return ToolResult(
                content=f"Error: Access denied. Path '{file_path}' is outside the workspace.",
                is_error=True,
            )

        if not os.path.exists(full_path):
            return ToolResult(
                content=f"Error: File not found: {file_path}",
                is_error=True,
            )

        if os.path.isdir(full_path):
            # List directory contents
            items = os.listdir(full_path)
            return ToolResult(content="\n".join(items))

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            offset = input.get("offset", 0)
            limit = input.get("limit", len(lines))
            selected = lines[offset : offset + limit]

            # Format with line numbers
            result_lines = []
            for i, line in enumerate(selected, start=offset + 1):
                result_lines.append(f"{i}\t{line.rstrip()}")

            return ToolResult(content="\n".join(result_lines))
        except UnicodeDecodeError:
            return ToolResult(
                content=f"Error: Cannot read '{file_path}' as text (binary file).",
                is_error=True,
            )
        except Exception as e:
            return ToolResult(content=f"Error reading file: {str(e)}", is_error=True)
