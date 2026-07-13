"""Model/provider clients for the pipeline. Registers the default provider."""

from gulp_shared.llm.anthropic_provider import AnthropicProvider
from gulp_shared.llm.base import (
    ChatMessage,
    ContentPart,
    DoneEvent,
    ImagePart,
    LLMAuthError,
    LLMCapabilityError,
    LLMError,
    LLMNotConfiguredError,
    LLMProvider,
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
from gulp_shared.llm.service import (
    complete_structured,
    get_provider,
    register_provider,
)

register_provider("anthropic", AnthropicProvider())

__all__ = [
    "AnthropicProvider",
    "ChatMessage",
    "ContentPart",
    "DoneEvent",
    "ImagePart",
    "LLMAuthError",
    "LLMCapabilityError",
    "LLMError",
    "LLMNotConfiguredError",
    "LLMProvider",
    "LLMRateLimitError",
    "ModelConfig",
    "StreamEvent",
    "TextDelta",
    "TextPart",
    "ToolCall",
    "ToolCallEvent",
    "ToolSpec",
    "UsageEvent",
    "complete_structured",
    "get_provider",
    "register_provider",
]
