"""Model/provider clients for the pipeline, resolved via the static catalog."""

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
from gulp_shared.llm.catalog import (
    PROVIDERS,
    ModelInfo,
    ProviderSpec,
    check_capabilities,
    get_spec,
)
from gulp_shared.llm.loop import ToolExecutor, run_tool_loop
from gulp_shared.llm.openai_compat import OpenAICompatProvider
from gulp_shared.llm.resolve import ping_credential, resolve_model_config
from gulp_shared.llm.service import complete_structured, get_provider

__all__ = [
    "PROVIDERS",
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
    "ModelInfo",
    "OpenAICompatProvider",
    "ProviderSpec",
    "StreamEvent",
    "TextDelta",
    "TextPart",
    "ToolCall",
    "ToolCallEvent",
    "ToolSpec",
    "UsageEvent",
    "ToolExecutor",
    "check_capabilities",
    "complete_structured",
    "get_provider",
    "get_spec",
    "ping_credential",
    "resolve_model_config",
    "run_tool_loop",
]
