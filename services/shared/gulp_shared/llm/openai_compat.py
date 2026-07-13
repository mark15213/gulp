"""OpenAI-compatible adapter — one wire format covers OpenAI, DeepSeek, and
Qwen (DashScope compatible-mode). Structured output via a forced function
call; clients build per call from `config` (BYOK)."""

import json
from collections.abc import AsyncIterator
from typing import Any, cast

import openai
from openai import AsyncOpenAI

from gulp_shared.llm.base import (
    ChatMessage,
    DoneEvent,
    LLMAuthError,
    LLMError,
    LLMRateLimitError,
    ModelConfig,
    StreamEvent,
    TextDelta,
    TextPart,
    ToolCall,
    ToolCallEvent,
    ToolSpec,
    UsageEvent,
)

_TOOL_NAME = "emit"
_STOP_REASONS = {"stop": "stop", "tool_calls": "tool_use", "length": "max_tokens"}


def _content(msg: ChatMessage) -> Any:
    if isinstance(msg.content, str):
        return msg.content
    parts: list[dict[str, Any]] = []
    for part in msg.content:
        if isinstance(part, TextPart):
            parts.append({"type": "text", "text": part.text})
        else:
            parts.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{part.media_type};base64,{part.data_b64}"},
                }
            )
    return parts


def _serialize(system: str | None, messages: list[ChatMessage]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if system is not None:
        out.append({"role": "system", "content": system})
    for m in messages:
        if m.role == "tool":
            out.append(
                {
                    "role": "tool",
                    "tool_call_id": m.tool_call_id,
                    "content": m.content if isinstance(m.content, str) else "",
                }
            )
        elif m.role == "assistant" and m.tool_calls:
            out.append(
                {
                    "role": "assistant",
                    "content": m.content if isinstance(m.content, str) else None,
                    "tool_calls": [
                        {
                            "id": c.id,
                            "type": "function",
                            "function": {"name": c.name, "arguments": json.dumps(c.arguments)},
                        }
                        for c in m.tool_calls
                    ],
                }
            )
        else:
            out.append({"role": m.role, "content": _content(m)})
    return out


def _tool_param(t: ToolSpec) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {"name": t.name, "description": t.description, "parameters": t.input_schema},
    }


class OpenAICompatProvider:
    def __init__(self, client: Any | None = None) -> None:
        self._client = client

    def _get_client(self, config: ModelConfig) -> Any:
        if self._client is not None:
            return self._client
        return AsyncOpenAI(api_key=config.api_key.get_secret_value(), base_url=config.base_url)

    async def complete_json(
        self,
        *,
        system: str | None,
        messages: list[ChatMessage],
        json_schema: dict[str, Any],
        config: ModelConfig,
    ) -> dict[str, Any]:
        try:
            resp = await self._get_client(config).chat.completions.create(
                model=config.model,
                max_tokens=config.max_tokens,
                temperature=config.temperature,
                messages=_serialize(system, messages),
                tools=[
                    _tool_param(
                        ToolSpec(
                            name=_TOOL_NAME,
                            description="Return the structured result for this task.",
                            input_schema=json_schema,
                        )
                    )
                ],
                tool_choice={"type": "function", "function": {"name": _TOOL_NAME}},
            )
        except openai.AuthenticationError as exc:
            raise LLMAuthError(str(exc)) from exc
        except openai.RateLimitError as exc:
            raise LLMRateLimitError(str(exc)) from exc
        for call in resp.choices[0].message.tool_calls or []:
            if call.function.name == _TOOL_NAME:
                return cast(dict[str, Any], json.loads(call.function.arguments))
        raise LLMError("response contained no forced function call")

    async def stream_chat(
        self,
        *,
        system: str | None,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None,
        config: ModelConfig,
    ) -> AsyncIterator[StreamEvent]:
        kwargs: dict[str, Any] = {
            "model": config.model,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "messages": _serialize(system, messages),
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            kwargs["tools"] = [_tool_param(t) for t in tools]
        pending: dict[int, dict[str, Any]] = {}
        finish = "stop"
        usage: Any = None
        try:
            stream = await self._get_client(config).chat.completions.create(**kwargs)
            async for chunk in stream:
                usage = getattr(chunk, "usage", None) or usage
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                if getattr(choice.delta, "content", None):
                    yield TextDelta(text=choice.delta.content)
                for tc in getattr(choice.delta, "tool_calls", None) or []:
                    slot = pending.setdefault(tc.index, {"id": "", "name": "", "arguments": ""})
                    slot["id"] = tc.id or slot["id"]
                    if tc.function is not None:
                        slot["name"] = tc.function.name or slot["name"]
                        slot["arguments"] += tc.function.arguments or ""
                if choice.finish_reason:
                    finish = choice.finish_reason
        except openai.AuthenticationError as exc:
            raise LLMAuthError(str(exc)) from exc
        except openai.RateLimitError as exc:
            raise LLMRateLimitError(str(exc)) from exc
        for i in sorted(pending):
            slot = pending[i]
            yield ToolCallEvent(
                tool_call=ToolCall(
                    id=slot["id"],
                    name=slot["name"],
                    arguments=json.loads(slot["arguments"] or "{}"),
                )
            )
        if usage is not None:
            yield UsageEvent(
                input_tokens=usage.prompt_tokens, output_tokens=usage.completion_tokens
            )
        yield DoneEvent(stop_reason=_STOP_REASONS.get(finish, finish))
