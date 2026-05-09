import subprocess
import tempfile
import os
from app.tools.base import Tool, ToolResult, ToolContext


class ExecutePythonTool(Tool):
    @property
    def name(self) -> str:
        return "execute_python"

    @property
    def description(self) -> str:
        return "Execute Python code. Returns stdout and stderr. Timeout defaults to 30 seconds."

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The Python code to execute.",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Execution timeout in seconds (default: 30).",
                },
            },
            "required": ["code"],
        }

    async def execute(self, input: dict, context: ToolContext) -> ToolResult:
        code = input["code"]
        timeout = input.get("timeout", 30)

        try:
            result = subprocess.run(
                ["python3", "-c", code],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=context.working_dir,
            )
            output_parts = []
            if result.stdout:
                output_parts.append(result.stdout.strip())
            if result.stderr:
                output_parts.append(f"[stderr]\n{result.stderr.strip()}")
            if result.returncode != 0:
                output_parts.append(f"[exit code: {result.returncode}]")

            output = "\n".join(output_parts) if output_parts else "(no output)"
            return ToolResult(
                content=output,
                is_error=(result.returncode != 0),
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                content=f"Error: Execution timed out after {timeout}s.",
                is_error=True,
            )
        except FileNotFoundError:
            return ToolResult(
                content="Error: python3 not found. Please ensure Python is installed.",
                is_error=True,
            )
        except Exception as e:
            return ToolResult(content=f"Error: {str(e)}", is_error=True)
