"""LLM service — OpenAI-compatible API client for local deployment."""

import json
import logging
import time
from typing import AsyncGenerator
import httpx
from app.config import get_settings

logger = logging.getLogger("llm")
settings = get_settings()


class LLMError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message


async def chat_stream(
    model_id: str,
    messages: list[dict],
    tools: list[dict],
    api_base: str | None = None,
) -> AsyncGenerator[dict, None]:
    """Stream chat completion from OpenAI-compatible API.

    Yields dicts: {"type": "text", "content": "..."} or {"type": "tool_use", ...}
    """
    url = f"{api_base or settings.llm_api_base}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.llm_api_key}",
    }
    payload = {
        "model": model_id,
        "messages": messages,
        "stream": True,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    msg_count = len(messages)
    tool_count = len(tools)
    start = time.time()
    logger.info("LLM stream -> %s, model=%s, messages=%d, tools=%d", url, model_id, msg_count, tool_count)

    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=10.0)) as client:
        try:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                if response.status_code != 200:
                    logger.warning("LLM stream returned %s", response.status_code)
                    body = await response.aread()
                    raise LLMError(
                        "MODEL_UNAVAILABLE",
                        f"LLM API returned {response.status_code}: {body.decode()[:500]}",
                    )

                tool_calls_buffer: dict[int, dict] = {}  # index -> {id, name, arguments}
                content_buffer = ""

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue

                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break

                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    delta = (data.get("choices") or [{}])[0].get("delta", {})

                    # Handle text content
                    text = delta.get("content", "")
                    if text:
                        content_buffer += text
                        yield {"type": "text", "content": text}

                    # Handle tool calls
                    tool_calls = delta.get("tool_calls") or []
                    for tc in tool_calls:
                        idx = tc.get("index", 0)
                        if idx not in tool_calls_buffer:
                            tool_calls_buffer[idx] = {
                                "id": tc.get("id", ""),
                                "name": "",
                                "arguments": "",
                            }

                        buf = tool_calls_buffer[idx]
                        if tc.get("id"):
                            buf["id"] = tc["id"]
                        if tc.get("function", {}).get("name"):
                            buf["name"] = tc["function"]["name"]
                        if tc.get("function", {}).get("arguments"):
                            buf["arguments"] += tc["function"]["arguments"]

                # After stream ends, emit complete tool calls
                for buf in tool_calls_buffer.values():
                    if buf["name"]:
                        try:
                            args = json.loads(buf["arguments"]) if buf["arguments"] else {}
                        except json.JSONDecodeError:
                            args = {}
                        yield {
                            "type": "tool_use",
                            "tool_use_id": buf["id"],
                            "tool_name": buf["name"],
                            "input": args,
                        }

        except httpx.TimeoutException as e:
            elapsed = time.time() - start
            raise LLMError(
                "MODEL_TIMEOUT",
                f"LLM API timed out after {elapsed:.0f}s (messages={msg_count}, tools={tool_count})",
            ) from e


async def chat_simple(
    model_id: str,
    messages: list[dict],
    tools: list[dict] | None = None,
    api_base: str | None = None,
) -> dict:
    """Non-streaming chat completion."""
    url = f"{api_base or settings.llm_api_base}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.llm_api_key}",
    }
    payload = {
        "model": model_id,
        "messages": messages,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                raise LLMError(
                    "MODEL_UNAVAILABLE",
                    f"LLM API returned {response.status_code}: {response.text[:500]}",
                )
            return response.json()
        except httpx.TimeoutException as e:
            raise LLMError(
                "MODEL_TIMEOUT",
                f"LLM API timed out (model={model_id})",
            ) from e
