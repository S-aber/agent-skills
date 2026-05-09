"""Agent service — core tool-calling loop (modeled after claude-code-ts src/query.ts)."""

import json
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.conversation import Conversation
from app.models.skill import Skill
from app.models.message import Message as MessageModel
from app.tools.base import Tool, ToolResult, ToolContext
from app.tools.registry import ToolRegistry, get_builtin_tools
from app.services import skill_service
from app.services.llm_service import chat_stream, LLMError
from app.config import get_settings

settings = get_settings()

MAX_TOOL_CALLS = 20

SYSTEM_PROMPT = """You are an AI Agent with access to tools to help users complete tasks.

## Available Tools
You have access to built-in tools (file operations, code execution, web access) and skill tools that represent specialized capabilities.

## Tool Usage Guidelines
- Use tools when they help accomplish the user's task
- Read files before editing them
- Execute code to verify solutions
- Search the web for current information when needed
- When a skill tool is called, its full instructions will be provided — follow them carefully

## Response Style
- Respond in the user's language
- Be concise and direct
- Explain what you're doing before calling tools
"""


class SkillTool(Tool):
    """A tool that represents an activated Skill. Like claude-code-ts SkillTool."""

    def __init__(self, skill: Skill, skill_content: str):
        self._skill = skill
        self._skill_content = skill_content

    @property
    def name(self) -> str:
        return self._skill.name

    @property
    def description(self) -> str:
        return self._skill.description

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    async def execute(self, input: dict, context: ToolContext) -> ToolResult:
        """Return the full SKILL.md content as the tool result, so LLM can follow the instructions."""
        return ToolResult(content=self._skill_content)


async def _build_tool_registry(
    db: AsyncSession, activated_skill_ids: list[str]
) -> tuple[ToolRegistry, list[Skill]]:
    """Build tool registry: built-in tools + activated skills as tools."""
    registry = ToolRegistry()

    activated_skills: list[Skill] = []
    for skill_id in activated_skill_ids:
        skill = await skill_service.get_skill_by_id(db, skill_id)
        if skill:
            activated_skills.append(skill)
            try:
                content = await skill_service.get_skill_content(skill.id)
                skill_tool = SkillTool(skill, content)
                registry.register(skill_tool)
            except skill_service.SkillError:
                pass  # Skip skills with missing files

    return registry, activated_skills


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

    # Build tool registry
    registry, skills = await _build_tool_registry(db, activated_skill_ids)

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

    # Build system prompt with skill info
    system_prompt = SYSTEM_PROMPT
    if skills:
        skill_list = "\n".join(f"- **{s.name}**: {s.description}" for s in skills)
        system_prompt += f"\n\n## Activated Skills\n{skill_list}"

    messages = [
        {"role": "system", "content": system_prompt},
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
                        result = await tool.execute(tool_input, tool_context)
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
                    else:
                        yield f"event: error\ndata: {json.dumps({'type': 'error', 'code': 'TOOL_NOT_FOUND', 'message': f'Tool not found: {tool_name}'})}\n\n"

        except LLMError as e:
            yield f"event: error\ndata: {json.dumps({'type': 'error', 'code': e.code, 'message': e.message})}\n\n"
            break
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'type': 'error', 'code': 'INTERNAL_ERROR', 'message': str(e)})}\n\n"
            break

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
