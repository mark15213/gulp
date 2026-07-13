"""Anthropic adapter — structured output via forced tool use; streaming via the
Messages streaming API. Clients build per call from `config.api_key` (BYOK);
tests inject a fake via `client`."""

from collections.abc import AsyncIterator
from typing import Any, cast

import anthropic
from anthropic import AsyncAnthropic

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
_STOP_REASONS = {"end_turn": "stop", "tool_use": "tool_use", "max_tokens": "max_tokens"}


def _content_blocks(msg: ChatMessage) -> str | list[dict[str, Any]]:
    if isinstance(msg.content, str):
        return msg.content
    blocks: list[dict[str, Any]] = []
    for part in msg.content:
        if isinstance(part, TextPart):
            blocks.append({"type": "text", "text": part.text})
        else:
            blocks.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": part.media_type,
                        "data": part.data_b64,
                    },
                }
            )
    return blocks


def _serialize(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in messages:
        if m.role == "system":
            raise LLMError("system prompts go in the `system` parameter, not messages")
        if m.role == "tool":
            out.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": m.tool_call_id,
                            "content": m.content if isinstance(m.content, str) else "",
                        }
                    ],
                }
            )
        elif m.role == "assistant" and m.tool_calls:
            blocks: list[dict[str, Any]] = []
            if isinstance(m.content, str) and m.content:
                blocks.append({"type": "text", "text": m.content})
            blocks += [
                {"type": "tool_use", "id": c.id, "name": c.name, "input": c.arguments}
                for c in m.tool_calls
            ]
            out.append({"role": "assistant", "content": blocks})
        else:
            out.append({"role": m.role, "content": _content_blocks(m)})
    return out


class AnthropicProvider:
    def __init__(self, client: Any | None = None) -> None:
        self._client = client

    def _get_client(self, config: ModelConfig) -> Any:
        if self._client is not None:
            return self._client
        return AsyncAnthropic(api_key=config.api_key.get_secret_value())

    async def complete_json(
        self,
        *,
        system: str | None,
        messages: list[ChatMessage],
        json_schema: dict[str, Any],
        config: ModelConfig,
    ) -> dict[str, Any]:
        tool = {
            "name": _TOOL_NAME,
            "description": "Return the structured result for this task.",
            "input_schema": json_schema,
        }
        kwargs: dict[str, Any] = {
            "model": config.model,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "messages": _serialize(messages),
            "tools": [tool],
            "tool_choice": {"type": "tool", "name": _TOOL_NAME},
        }
        if system is not None:
            kwargs["system"] = system
        try:
            resp = await self._get_client(config).messages.create(**kwargs)
        except anthropic.AuthenticationError as exc:
            raise LLMAuthError(str(exc)) from exc
        except anthropic.RateLimitError as exc:
            raise LLMRateLimitError(str(exc)) from exc
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use":
                return cast(dict[str, Any], block.input)
        raise LLMError("Anthropic response contained no tool_use block")

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
            "messages": _serialize(messages),
        }
        if system is not None:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": t.input_schema}
                for t in tools
            ]
        try:
            async with self._get_client(config).messages.stream(**kwargs) as stream:
                async for event in stream:
                    if (
                        getattr(event, "type", None) == "content_block_delta"
                        and getattr(event.delta, "type", None) == "text_delta"
                    ):
                        yield TextDelta(text=event.delta.text)
                final = await stream.get_final_message()
        except anthropic.AuthenticationError as exc:
            raise LLMAuthError(str(exc)) from exc
        except anthropic.RateLimitError as exc:
            raise LLMRateLimitError(str(exc)) from exc
        for block in final.content:
            if getattr(block, "type", None) == "tool_use":
                yield ToolCallEvent(
                    tool_call=ToolCall(
                        id=block.id, name=block.name, arguments=cast(dict[str, Any], block.input)
                    )
                )
        usage = getattr(final, "usage", None)
        if usage is not None:
            yield UsageEvent(input_tokens=usage.input_tokens, output_tokens=usage.output_tokens)
        stop = final.stop_reason or "stop"
        yield DoneEvent(stop_reason=_STOP_REASONS.get(stop, stop))
