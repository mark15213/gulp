from typing import Any

import pytest

from gulp_shared.llm.anthropic_provider import AnthropicProvider
from gulp_shared.llm.base import LLMError, ModelConfig


class _ToolUseBlock:
    type = "tool_use"

    def __init__(self, data: dict[str, Any]) -> None:
        self.input = data


class _TextBlock:
    type = "text"
    text = "ignored"


class _Resp:
    def __init__(self, content: list[Any]) -> None:
        self.content = content


class _Messages:
    def __init__(self, resp: _Resp) -> None:
        self._resp = resp
        self.last_kwargs: dict[str, Any] | None = None

    async def create(self, **kwargs: Any) -> _Resp:
        self.last_kwargs = kwargs
        return self._resp


class _FakeClient:
    def __init__(self, resp: _Resp) -> None:
        self.messages = _Messages(resp)


async def test_returns_tool_use_input_and_forces_the_tool() -> None:
    resp = _Resp([_TextBlock(), _ToolUseBlock({"name": "Ada", "age": 36})])
    client = _FakeClient(resp)
    prov = AnthropicProvider(client=client)

    out = await prov.complete_json(
        system="be precise",
        messages=[{"role": "user", "content": "who?"}],
        json_schema={"type": "object", "properties": {"name": {"type": "string"}}},
        config=ModelConfig(model="claude-sonnet-4-6"),
    )
    assert out == {"name": "Ada", "age": 36}
    kw = client.messages.last_kwargs
    assert kw is not None
    assert kw["model"] == "claude-sonnet-4-6"
    assert kw["tool_choice"] == {"type": "tool", "name": "emit"}
    assert kw["tools"][0]["input_schema"]["type"] == "object"
    assert kw["system"] == "be precise"


async def test_raises_when_no_tool_use_block() -> None:
    client = _FakeClient(_Resp([_TextBlock()]))
    prov = AnthropicProvider(client=client)
    with pytest.raises(LLMError):
        await prov.complete_json(
            system=None,
            messages=[{"role": "user", "content": "hi"}],
            json_schema={"type": "object"},
            config=ModelConfig(),
        )
