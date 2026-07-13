"""Anthropic adapter — structured output via forced tool use (S2 design §2.6).

The client is injectable so tests pass a fake; in production it is built lazily
from settings so importing/registering this module needs no API key.
"""

from collections.abc import AsyncIterator
from typing import Any, cast

from anthropic import AsyncAnthropic

from gulp_shared.llm.base import ChatMessage, LLMError, ModelConfig, StreamEvent, ToolSpec
from gulp_shared.settings import settings

_TOOL_NAME = "emit"


class AnthropicProvider:
    def __init__(self, client: Any | None = None) -> None:
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        return self._client

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
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "tools": [tool],
            "tool_choice": {"type": "tool", "name": _TOOL_NAME},
        }
        if system is not None:
            kwargs["system"] = system
        resp = await self._get_client().messages.create(**kwargs)
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
        raise NotImplementedError("streaming lands with the adapter rework")
        yield  # pragma: no cover — makes this an async generator
