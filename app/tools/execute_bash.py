import asyncio
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
        command = input.get("command")
        if not command:
            return ToolResult(
                content="Error: Missing required parameter 'command'.",
                is_error=True,
            )
        timeout = input.get("timeout", 30)

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=context.working_dir,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return ToolResult(
                    content=f"Error: Command timed out after {timeout}s.",
                    is_error=True,
                )

            stdout_str = stdout.decode("utf-8", errors="replace") if stdout else ""
            stderr_str = stderr.decode("utf-8", errors="replace") if stderr else ""

            output_parts = []
            if stdout_str.strip():
                output_parts.append(stdout_str.strip())
            if stderr_str.strip():
                output_parts.append(f"[stderr]\n{stderr_str.strip()}")
            if process.returncode != 0:
                output_parts.append(f"[exit code: {process.returncode}]")

            output = "\n".join(output_parts) if output_parts else "(no output)"
            return ToolResult(
                content=output,
                is_error=(process.returncode != 0),
            )
        except Exception as e:
            return ToolResult(content=f"Error: {str(e)}", is_error=True)
