"""Provider registry + the validated `complete_structured` entry point."""


from pydantic import BaseModel, ValidationError

from gulp_shared.llm.base import ChatMessage, LLMError, LLMProvider, ModelConfig

_PROVIDERS: dict[str, LLMProvider] = {}


def register_provider(name: str, provider: LLMProvider) -> None:
    _PROVIDERS[name] = provider


def get_provider(name: str) -> LLMProvider:
    try:
        return _PROVIDERS[name]
    except KeyError as exc:
        raise LLMError(f"no LLM provider registered as {name!r}") from exc


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
    prov = provider or get_provider(cfg.provider)
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
