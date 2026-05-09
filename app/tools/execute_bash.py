import subprocess
from app.tools.base import Tool, ToolResult, ToolContext


class ExecuteBashTool(Tool):
    @property
    def name(self) -> str:
        return "execute_bash"

    @property
    def description(self) -> str:
        return "Execute a bash shell command. Returns stdout and stderr. Use for file operations, git, package management, etc."

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute.",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Execution timeout in seconds (default: 30).",
                },
            },
            "required": ["command"],
        }

    async def execute(self, input: dict, context: ToolContext) -> ToolResult:
        command = input["command"]
        timeout = input.get("timeout", 30)

        try:
            result = subprocess.run(
                command,
                shell=True,
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
                content=f"Error: Command timed out after {timeout}s.",
                is_error=True,
            )
        except Exception as e:
            return ToolResult(content=f"Error: {str(e)}", is_error=True)
