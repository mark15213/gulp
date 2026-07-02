"""Provider-agnostic LLM contract (S2 design §2.6)."""

from typing import Any, Protocol

from pydantic import BaseModel

Message = dict[str, str]


class LLMError(Exception):
    """Raised on provider failure or when output can't be validated."""


class ModelConfig(BaseModel):
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-6"
    max_tokens: int = 4096
    temperature: float = 0.2


class LLMProvider(Protocol):
    async def complete_json(
        self,
        *,
        system: str | None,
        messages: list[Message],
        json_schema: dict[str, Any],
        config: ModelConfig,
    ) -> dict[str, Any]: ...
