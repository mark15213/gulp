"""Model/provider clients for the pipeline. Registers the default provider."""

from app.llm.anthropic_provider import AnthropicProvider
from app.llm.base import LLMError, LLMProvider, Message, ModelConfig
from app.llm.service import (
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
