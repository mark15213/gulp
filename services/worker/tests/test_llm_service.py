from typing import Any

import pytest
from gulp_shared.llm.base import LLMError, Message, ModelConfig
from gulp_shared.llm.service import complete_structured, get_provider, register_provider
from pydantic import BaseModel


class Person(BaseModel):
    name: str
    age: int


class FakeProvider:
    """Returns queued dicts in order; lets us simulate invalid-then-valid."""

    def __init__(self, *responses: dict[str, Any]) -> None:
        self._responses = list(responses)
        self.calls = 0

    async def complete_json(
        self,
        *,
        system: str | None,
        messages: list[Message],
        json_schema: dict[str, Any],
        config: ModelConfig,
    ) -> dict[str, Any]:
        self.calls += 1
        return self._responses.pop(0)


async def test_complete_structured_validates_into_model() -> None:
    fake = FakeProvider({"name": "Ada", "age": 36})
    out = await complete_structured(
        response_model=Person,
        messages=[{"role": "user", "content": "who?"}],
        config=ModelConfig(),
        provider=fake,
    )
    assert isinstance(out, Person) and out.name == "Ada" and out.age == 36
    assert fake.calls == 1


async def test_complete_structured_retries_then_succeeds() -> None:
    fake = FakeProvider({"name": "Ada"}, {"name": "Ada", "age": 36})  # 1st missing age
    out = await complete_structured(
        response_model=Person,
        messages=[{"role": "user", "content": "who?"}],
        config=ModelConfig(),
        provider=fake,
        max_attempts=2,
    )
    assert out.age == 36
    assert fake.calls == 2


async def test_complete_structured_raises_after_max_attempts() -> None:
    fake = FakeProvider({"name": "x"}, {"name": "y"})  # both invalid
    with pytest.raises(LLMError):
        await complete_structured(
            response_model=Person,
            messages=[{"role": "user", "content": "who?"}],
            config=ModelConfig(),
            provider=fake,
            max_attempts=2,
        )


def test_registry_round_trips() -> None:
    fake = FakeProvider({"name": "z", "age": 1})
    register_provider("fake", fake)
    assert get_provider("fake") is fake


def test_get_provider_unknown_raises() -> None:
    with pytest.raises(LLMError):
        get_provider("nope-not-registered")
