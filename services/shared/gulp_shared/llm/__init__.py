"""Model/provider clients for the pipeline. Registers the default provider."""

from gulp_shared.llm.anthropic_provider import AnthropicProvider
from gulp_shared.llm.base import LLMError, LLMProvider, Message, ModelConfig
from gulp_shared.llm.service import (
    complete_structured,
    get_provider,
    register_provider,
)

register_provider("anthropic", AnthropicProvider())

__all__ = [
    "AnthropicProvider",
    "LLMError",
    "LLMProvider",
    "Message",
    "ModelConfig",
    "complete_structured",
    "get_provider",
    "register_provider",
]
