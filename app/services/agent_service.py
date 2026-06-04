"""Agent service — core tool-calling loop (modeled after claude-code-ts src/query.ts)."""

import json
import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.conversation import Conversation
from app.models.skill import Skill
from app.models.message import Message as MessageModel
from app.models.mcp_server import MCPServer
from app.tools.base import Tool, ToolResult, ToolContext
from app.tools.registry import ToolRegistry, get_builtin_tools
from app.services import skill_service
from app.services.llm_service import chat_stream, LLMError
from app.services.mcp_manager import mcp_manager
from app.config import get_settings

logger = logging.getLogger("agent")

settings = get_settings()

MAX_TOOL_CALLS = 20

SYSTEM_PROMPT = """You are an AI Agent with access to tools to help users complete tasks.

## Available Tools
You have access to built-in tools: read_file, write_file, execute_python, execute_bash, web_fetch, web_search.

When skills are activated, a "Skill" tool is also available. Use the Skill tool to invoke skills — it provides specialized instructions for specific tasks.

MCP tools (prefixed with mcp__) provide additional capabilities from external MCP servers. Use them as needed.

## Tool Usage Guidelines
- Use tools when they help accomplish the user's task
- Read files before editing them
- Execute code to verify solutions
- Search the web for current information when needed

## File Formats
- For text files (.txt, .md, .json, .py, .html, .css, .js, etc.): use write_file directly
- For binary formats (.docx, .xlsx, .pdf, .png, etc.): you MUST use execute_python to generate them
  - .docx: use python-docx library (from docx import Document)
  - .xlsx: use openpyxl library
  - .pdf: use reportlab or fpdf library
  - Example for docx: write Python code that creates a Document, adds content, and saves

## Response Style
- Respond in the user's language
- Be concise and direct
- Explain what you're doing before calling tools
"""

SKILL_TOOL_INSTRUCTIONS = """Execute a skill within the main conversation

<skills-instructions>
When users ask you to perform tasks, check if any of the available skills below can help complete the task more effectively. Skills provide specialized capabilities and domain knowledge.

How to use skills:
- Invoke skills using this tool with the skill name only (no arguments)
- When you invoke a skill, you will see the full skill instructions which define the workflow to follow
- Examples:
  - `skill: "pdf"` — invoke the pdf skill
  - `skill: "xlsx"` — invoke the xlsx skill
  - `skill: "docx"` — invoke the docx skill

Important:
- Only use skills listed in <available_skills> below
- When a skill matches the user's request, invoke the Skill tool BEFORE generating any other response about the task
- You may invoke multiple skills if the task requires it
- Do NOT invoke a skill that is already in context
</skills-instructions>

<available_skills>
{skills_list}
</available_skills>
"""


class SkillTool(Tool):
    """Unified Skill tool — like claude-code-ts SkillTool.

    One tool lists all available skills. LLM invokes it by name to get
    the full SKILL.md content injected as the tool result.
    """

    def __init__(self, skills: list[dict]):
        self._skills: dict[str, dict] = {}
        for s in skills:
            self._skills[s["name"]] = s

    @property
    def name(self) -> str:
        return "Skill"

    @property
    def description(self) -> str:
        lines = []
        for s in self._skills.values():
            lines.append(f"- {s['name']}: {s['description']}")
        skills_text = "\n".join(lines) if lines else "(no skills activated)"
        return SKILL_TOOL_INSTRUCTIONS.replace("{skills_list}", skills_text)

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "skill": {
                    "type": "string",
                    "description": "The skill name to invoke. Must match an available skill name exactly.",
                },
            },
            "required": ["skill"],
        }

    async def execute(self, input: dict, context: ToolContext) -> ToolResult:
        skill_name = input.get("skill", "").strip()

        if not skill_name:
            return ToolResult(
                content="Error: No skill name provided. Use the skill name from the available skills list.",
                is_error=True,
            )

        skill = self._skills.get(skill_name)
        if not skill:
            available = ", ".join(self._skills.keys()) or "(none)"
            return ToolResult(
                content=f"Error: Skill '{skill_name}' not found. Available skills: {available}",
                is_error=True,
            )

        try:
            content = await skill_service.get_skill_content(skill["id"])
            return ToolResult(
                content=f"Launching skill: {skill_name}\n\n{content}"
            )
        except skill_service.SkillError as e:
            return ToolResult(
                content=f"Error loading skill '{skill_name}': {e.message}",
                is_error=True,
            )


async def _load_skills_meta(
    db: AsyncSession, activated_skill_ids: list[str]
) -> list[dict]:
    """Load activated skills metadata (id, name, description) for SkillTool listing.

    Full SKILL.md content is loaded on demand when the Skill tool is invoked.
    """
    skills_meta: list[dict] = []

    for skill_id in activated_skill_ids:
        skill = await skill_service.get_skill_by_id(db, skill_id)
        if skill:
            skills_meta.append({
                "id": skill.id,
                "name": skill.name,
                "description": skill.description,
            })
        else:
            logger.warning("Skill %s not found in DB", skill_id)

    return skills_meta


async def _load_mcp_tools(
    db: AsyncSession, workspace_id: str, registry: ToolRegistry
) -> int:
    """Load enabled MCP server configs, connect, fetch tools, register in registry.

    Returns number of MCP tools registered.
    """
    result = await db.execute(
        select(MCPServer).where(
            MCPServer.workspace_id == workspace_id,
            MCPServer.enabled == True,
        )
    )
    servers = result.scalars().all()

    total_count = 0
    for server in servers:
        try:
            wrappers = await mcp_manager.fetch_tools(server)
            for wrapper in wrappers:
                registry.register(wrapper)
            total_count += len(wrappers)
        except Exception as exc:
            logger.warning(
                "[mcp] Failed to load tools from server '%s': %s",
                server.name,
                exc,
            )
    return total_count


async def _build_history(db: AsyncSession, conversation_id: str) -> list[dict]:
    """Load conversation history from DB and format for LLM."""
    from sqlalchemy import select
    result = await db.execute(
        select(MessageModel)
        .where(MessageModel.conversation_id == conversation_id)
        .order_by(MessageModel.created_at.asc())
    )
    messages = result.scalars().all()

    history = []
    for msg in messages:
        if msg.role == "system":
            continue  # system prompt is handled separately
        entry = {"role": msg.role, "content": msg.content}
        if msg.tool_calls:
            entry["tool_calls"] = json.loads(msg.tool_calls)
        history.append(entry)
    return history


async def run_agent(
    db: AsyncSession,
    conversation: Conversation,
    user_content: str,
) -> AsyncGenerator[str, None]:
    """Core agent loop — like claude-code-ts query() function.

    Yields SSE-formatted strings (with 'event: ...\ndata: ...\n\n').
    """
    conv_id = conversation.id
    workspace_id = conversation.workspace_id
    model_id = conversation.model_id
    activated_skill_ids = json.loads(conversation.activated_skill_ids)

    logger.info("[conv=%s] Starting agent run, model=%s, skills=%d", conv_id[:8], model_id, len(activated_skill_ids))

    # Load skills metadata and create unified Skill tool
    skills_meta = await _load_skills_meta(db, activated_skill_ids)
    skill_tool = SkillTool(skills_meta)
    logger.info("[conv=%s] Loaded %d skills for Skill tool", conv_id[:8], len(skills_meta))

    # Build tool registry: built-in tools + Skill tool
    registry = ToolRegistry()
    if skills_meta:
        registry.register(skill_tool)
    logger.info("[conv=%s] Built registry: %d builtin + Skill tool", conv_id[:8], len(get_builtin_tools()))

    # Load and register MCP tools
    mcp_tool_count = await _load_mcp_tools(db, workspace_id, registry)
    if mcp_tool_count > 0:
        logger.info("[conv=%s] Registered %d MCP tools", conv_id[:8], mcp_tool_count)

    # Build working context
    tool_context = ToolContext(
        workspace_id=workspace_id,
        conversation_id=conv_id,
        working_dir=settings.workspace_storage_path,
    )

    # Store user message
    user_msg = MessageModel(
        conversation_id=conv_id,
        role="user",
        content=user_content,
    )
    db.add(user_msg)
    await db.commit()

    # Build history
    history = await _build_history(db, conv_id)

    # System prompt (skill content is NOT here — it's loaded on demand via Skill tool)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ] + history

    # Get tools as OpenAI format
    all_tools = registry.get_all()
    tool_defs = [t.to_openai_tool() for t in all_tools]

    # Main agent loop
    tool_call_count = 0
    total_input_tokens = 0
    total_output_tokens = 0

    while tool_call_count < MAX_TOOL_CALLS:
        # Send SSE: request start
        yield f"event: stream_request_start\ndata: {json.dumps({'type': 'stream_request_start'})}\n\n"

        assistant_content = ""
        assistant_tool_calls = []

        try:
            async for event in chat_stream(model_id, messages, tool_defs):
                if event["type"] == "text":
                    assistant_content += event["content"]
                    yield f"event: assistant\ndata: {json.dumps({'type': 'assistant', 'content': event['content']})}\n\n"

                elif event["type"] == "tool_use":
                    tool_name = event["tool_name"]
                    tool_input = event["input"]
                    tool_use_id = event["tool_use_id"]

                    assistant_tool_calls.append({
                        "id": tool_use_id,
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": json.dumps(tool_input),
                        },
                    })

                    # Notify frontend
                    yield f"event: tool_use\ndata: {json.dumps({'type': 'tool_use', 'tool_use_id': tool_use_id, 'tool_name': tool_name, 'input': tool_input})}\n\n"

                    # Execute the tool
                    tool = registry.get(tool_name)
                    if tool:
                        logger.debug("[conv=%s] Executing tool: %s", conv_id[:8], tool_name)
                        try:
                            result = await tool.execute(tool_input, tool_context)
                        except Exception as tool_exc:
                            logger.exception("[conv=%s] Tool %s execution failed", conv_id[:8], tool_name)
                            result = ToolResult(content=f"Tool execution error: {str(tool_exc)}", is_error=True)
                        status = "error" if result.is_error else "ok"
                        logger.info("[conv=%s] Tool %s completed (%s, %d chars)", conv_id[:8], tool_name, status, len(result.content))
                        yield f"event: tool_result\ndata: {json.dumps({'type': 'tool_result', 'tool_use_id': tool_use_id, 'tool_name': tool_name, 'content': result.content, 'is_error': result.is_error})}\n\n"

                        # Append assistant message with tool calls to history
                        assistant_msg = {
                            "role": "assistant",
                            "content": assistant_content or None,
                            "tool_calls": [
                                {
                                    "id": tool_use_id,
                                    "type": "function",
                                    "function": {
                                        "name": tool_name,
                                        "arguments": json.dumps(tool_input),
                                    },
                                }
                            ],
                        }
                        messages.append(assistant_msg)

                        # Append tool result
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_use_id,
                            "content": result.content,
                        })

                        tool_call_count += 1

                        # Enrich tool_calls entry with result for DB storage
                        assistant_tool_calls[-1]["result"] = result.content
                        assistant_tool_calls[-1]["is_error"] = result.is_error
                    else:
                        yield f"event: error\ndata: {json.dumps({'type': 'error', 'code': 'TOOL_NOT_FOUND', 'message': f'Tool not found: {tool_name}'})}\n\n"

        except LLMError as e:
            logger.error("[conv=%s] LLM error: [%s] %s", conv_id[:8], e.code, e.message)
            yield f"event: error\ndata: {json.dumps({'type': 'error', 'code': e.code, 'message': e.message})}\n\n"
            yield f"event: done\ndata: {json.dumps({'type': 'done', 'num_turns': tool_call_count})}\n\n"
            return
        except Exception as e:
            logger.exception("[conv=%s] Unexpected error in agent loop", conv_id[:8])
            yield f"event: error\ndata: {json.dumps({'type': 'error', 'code': 'INTERNAL_ERROR', 'message': str(e)})}\n\n"
            yield f"event: done\ndata: {json.dumps({'type': 'done', 'num_turns': tool_call_count})}\n\n"
            return

        # If no tool calls, this turn is complete
        if not assistant_tool_calls:
            # Save assistant message
            assistant_db_msg = MessageModel(
                conversation_id=conv_id,
                role="assistant",
                content=assistant_content,
            )
            db.add(assistant_db_msg)
            await db.commit()

            logger.info("[conv=%s] Agent run complete: %d tool calls, %d chars output", conv_id[:8], tool_call_count, len(assistant_content))
            yield f"event: done\ndata: {json.dumps({'type': 'done', 'usage': {'input_tokens': total_input_tokens, 'output_tokens': total_output_tokens}, 'num_turns': tool_call_count + 1})}\n\n"
            return

        # Save intermediate assistant message with tool calls
        assistant_db_msg = MessageModel(
            conversation_id=conv_id,
            role="assistant",
            content=assistant_content or "",
            tool_calls=json.dumps(assistant_tool_calls),
        )
        db.add(assistant_db_msg)
        await db.commit()

        # Reset for next iteration
        assistant_content = ""
        assistant_tool_calls = []

    # Max tool calls reached
    yield f"event: error\ndata: {json.dumps({'type': 'error', 'code': 'MAX_TOOL_CALLS_REACHED', 'message': f'Exceeded maximum of {MAX_TOOL_CALLS} tool calls'})}\n\n"
    yield f"event: done\ndata: {json.dumps({'type': 'done', 'usage': {'input_tokens': total_input_tokens, 'output_tokens': total_output_tokens}, 'num_turns': tool_call_count})}\n\n"
