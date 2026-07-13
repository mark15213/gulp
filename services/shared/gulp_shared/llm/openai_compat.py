"""OpenAI-compatible adapter — one wire format covers OpenAI, DeepSeek, and
Qwen (DashScope compatible-mode). Filled in by the adapter task."""

from collections.abc import AsyncIterator
from typing import Any

from gulp_shared.llm.base import ChatMessage, ModelConfig, StreamEvent, ToolSpec


class OpenAICompatProvider:
    def __init__(self, client: Any | None = None) -> None:
        self._client = client

    async def complete_json(
        self,
        *,
        system: str | None,
        messages: list[ChatMessage],
        json_schema: dict[str, Any],
        config: ModelConfig,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def stream_chat(
        self,
        *,
        system: str | None,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None,
        config: ModelConfig,
    ) -> AsyncIterator[StreamEvent]:
        raise NotImplementedError
        yield  # pragma: no cover — makes this an async generator
