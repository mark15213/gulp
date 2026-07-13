"""Provider-agnostic LLM contract (spec 2026-07-13 MaaS layer)."""

from collections.abc import AsyncIterator
from typing import Any, Literal, Protocol

from pydantic import BaseModel, SecretStr


class LLMError(Exception):
    """Raised on provider failure or when output can't be validated."""


class LLMNotConfiguredError(LLMError):
    """The user has no usable LLM credentials (and no dev fallback exists)."""


class LLMAuthError(LLMError):
    """The provider rejected the API key. Never retried."""


class LLMRateLimitError(LLMError):
    """The provider throttled the call (429)."""


class LLMCapabilityError(LLMError):
    """The request needs a capability this provider lacks (e.g. vision)."""


class TextPart(BaseModel):
    type: Literal["text"] = "text"
    text: str


class ImagePart(BaseModel):
    type: Literal["image"] = "image"
    media_type: str  # e.g. "image/png"
    data_b64: str


ContentPart = TextPart | ImagePart


class ToolSpec(BaseModel):
    """A tool declared to the model."""

    name: str
    description: str
    input_schema: dict[str, Any]


class ToolCall(BaseModel):
    """A call the model asked for."""

    id: str
    name: str
    arguments: dict[str, Any]


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | list[ContentPart] = ""
    tool_calls: list[ToolCall] | None = None  # assistant turns that invoked tools
    tool_call_id: str | None = None  # tool-result turns


class TextDelta(BaseModel):
    type: Literal["text_delta"] = "text_delta"
    text: str


class ToolCallEvent(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    tool_call: ToolCall


class UsageEvent(BaseModel):
    type: Literal["usage"] = "usage"
    input_tokens: int
    output_tokens: int


class DoneEvent(BaseModel):
    type: Literal["done"] = "done"
    stop_reason: str = "stop"  # "stop" | "tool_use" | "max_tokens" | provider-raw


StreamEvent = TextDelta | ToolCallEvent | UsageEvent | DoneEvent


class ModelConfig(BaseModel):
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-6"
    api_key: SecretStr = SecretStr("")
    base_url: str | None = None
    max_tokens: int = 4096
    temperature: float = 0.2


class LLMProvider(Protocol):
    async def complete_json(
        self,
        *,
        system: str | None,
        messages: list[ChatMessage],
        json_schema: dict[str, Any],
        config: ModelConfig,
    ) -> dict[str, Any]: ...

    def stream_chat(
        self,
        *,
        system: str | None,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None,
        config: ModelConfig,
    ) -> AsyncIterator[StreamEvent]: ...
