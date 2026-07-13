"""Validated `complete_structured` entry point over the provider catalog."""

from pydantic import BaseModel, ValidationError

from gulp_shared.llm.base import ChatMessage, LLMError, LLMProvider, ModelConfig
from gulp_shared.llm.catalog import check_capabilities, get_spec


def get_provider(name: str) -> LLMProvider:
    return get_spec(name).adapter


async def complete_structured[T: BaseModel](
    *,
    response_model: type[T],
    messages: list[ChatMessage],
    system: str | None = None,
    config: ModelConfig | None = None,
    provider: LLMProvider | None = None,
    max_attempts: int = 2,
) -> T:
    cfg = config or ModelConfig()
    if provider is None:
        spec = get_spec(cfg.provider)
        check_capabilities(spec, messages, None)
        prov: LLMProvider = spec.adapter
    else:
        prov = provider
    schema = response_model.model_json_schema()
    last: Exception | None = None
    for _ in range(max_attempts):
        raw = await prov.complete_json(
            system=system, messages=messages, json_schema=schema, config=cfg
        )
        try:
            return response_model.model_validate(raw)
        except ValidationError as exc:
            last = exc
    raise LLMError(
        f"{response_model.__name__} validation failed after {max_attempts} attempts"
    ) from last
