from app.tools.base import Tool, ToolResult, ToolContext


class WebSearchTool(Tool):
    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Search the web for information. Returns formatted search results. Use when you need current information beyond your knowledge cutoff."

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query string.",
                },
            },
            "required": ["query"],
        }

    async def execute(self, input: dict, context: ToolContext) -> ToolResult:
        query = input["query"]

        # Note: This is a stub implementation.
        # For a real implementation, you would integrate with:
        # - DuckDuckGo API (free, no key needed)
        # - Bing Search API
        # - Google Custom Search API
        # - SerpAPI / Serper.dev

        try:
            # Try DuckDuckGo HTML search (no API key needed)
            import httpx
            from urllib.parse import quote

            search_url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                response = await client.get(
                    search_url,
                    headers={"User-Agent": "AgentSkills/1.0"},
                )
                response.raise_for_status()

                # Extract result snippets using simple regex
                import re
                # Extract result titles and snippets
                result_pattern = re.compile(
                    r'<a[^>]*class="result__a"[^>]*>(.*?)</a>.*?<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
                    re.DOTALL,
                )
                matches = result_pattern.findall(response.text)

                if not matches:
                    return ToolResult(
                        content=f"No search results found for: {query}",
                    )

                lines = [f"Web search results for: {query}\n"]
                for i, (title, snippet) in enumerate(matches[:5], 1):
                    title_clean = re.sub(r"<[^>]+>", "", title).strip()
                    snippet_clean = re.sub(r"<[^>]+>", "", snippet).strip()
                    lines.append(f"{i}. {title_clean}")
                    lines.append(f"   {snippet_clean}\n")

                return ToolResult(content="\n".join(lines))

        except Exception as e:
            # If DuckDuckGo fails, provide a descriptive fallback
            return ToolResult(
                content=(
                    f"Web search is currently unavailable. Search query was: '{query}'\n"
                    f"Error: {str(e)}\n\n"
                    "To enable web search, configure a search API (DuckDuckGo, Bing, Google) "
                    "in the tool implementation."
                ),
                is_error=True,
            )
