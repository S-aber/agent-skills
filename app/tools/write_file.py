import os
import base64
from app.tools.base import Tool, ToolResult, ToolContext


class WriteFileTool(Tool):
    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return (
            "Create or overwrite a file in the workspace. "
            "For text files (code, markdown, json, etc.), use encoding='utf-8' (default). "
            "For binary files (docx, pdf, images, etc.), generate the file using execute_python "
            "(e.g., python-docx, reportlab) and write the output directly. "
            "If you must write binary data inline, use encoding='base64' and pass base64-encoded content."
        )

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to write, relative to workspace root.",
                },
                "content": {
                    "type": "string",
                    "description": "The content to write. For text files, plain text. For binary, use encoding='base64'.",
                },
                "encoding": {
                    "type": "string",
                    "enum": ["utf-8", "base64"],
                    "description": "Content encoding. 'utf-8' for text files (default), 'base64' for binary files.",
                },
            },
            "required": ["file_path", "content"],
        }

    async def execute(self, input: dict, context: ToolContext) -> ToolResult:
        file_path = input["file_path"]
        content = input["content"]
        encoding = input.get("encoding", "utf-8")
        full_path = os.path.join(context.working_dir, file_path)

        # Security: prevent path traversal
        real_path = os.path.realpath(full_path)
        real_workspace = os.path.realpath(context.working_dir)
        if not real_path.startswith(real_workspace):
            return ToolResult(
                content=f"Error: Access denied. Path '{file_path}' is outside the workspace.",
                is_error=True,
            )

        try:
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            if encoding == "base64":
                data = base64.b64decode(content)
                with open(full_path, "wb") as f:
                    f.write(data)
            else:
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content)
            return ToolResult(content=f"File written successfully: {file_path}")
        except Exception as e:
            return ToolResult(content=f"Error writing file: {str(e)}", is_error=True)
