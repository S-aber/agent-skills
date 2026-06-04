import httpx
from app.tools.base import Tool, ToolResult, ToolContext


class WebFetchTool(Tool):
    @property
    def name(self) -> str:
        return "web_fetch"

    @property
    def description(self) -> str:
        return "Fetch content from a URL and extract readable text. Use for reading documentation, API responses, or web pages."

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch content from.",
                },
            },
            "required": ["url"],
        }

    async def execute(self, input: dict, context: ToolContext) -> ToolResult:
        url = input.get("url")
        if not url:
            return ToolResult(
                content="Error: Missing required parameter 'url'.",
                is_error=True,
            )

        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                response = await client.get(url, headers={"User-Agent": "AgentSkills/1.0"})
                response.raise_for_status()

                content_type = response.headers.get("content-type", "")
                if "text/html" in content_type:
                    # Simple HTML to text: strip tags
                    import re
                    text = re.sub(r"<[^>]+>", " ", response.text)
                    text = re.sub(r"\s+", " ", text).strip()
                    # Truncate to avoid overwhelming context
                    if len(text) > 8000:
                        text = text[:8000] + "\n... (truncated)"
                    return ToolResult(content=text)
                else:
                    text = response.text
                    if len(text) > 8000:
                        text = text[:8000] + "\n... (truncated)"
                    return ToolResult(content=text)

        except httpx.HTTPStatusError as e:
            return ToolResult(
                content=f"Error: HTTP {e.response.status_code} when fetching {url}",
                is_error=True,
            )
        except httpx.TimeoutException:
            return ToolResult(content=f"Error: Timeout when fetching {url}", is_error=True)
        except Exception as e:
            return ToolResult(content=f"Error fetching URL: {str(e)}", is_error=True)
