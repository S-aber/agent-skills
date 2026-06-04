import asyncio
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
        code = input.get("code")
        if not code:
            return ToolResult(
                content="Error: Missing required parameter 'code'.",
                is_error=True,
            )
        timeout = input.get("timeout", 30)

        try:
            process = await asyncio.create_subprocess_exec(
                "python3", "-c", code,
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
                    content=f"Error: Execution timed out after {timeout}s.",
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
        except FileNotFoundError:
            return ToolResult(
                content="Error: python3 not found. Please ensure Python is installed.",
                is_error=True,
            )
        except Exception as e:
            return ToolResult(content=f"Error: {str(e)}", is_error=True)
