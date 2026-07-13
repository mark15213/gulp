"""OpenAI-compatible adapter: serialization, forced function call, stream aggregation."""

from types import SimpleNamespace
from typing import Any

from gulp_shared.llm.base import ChatMessage, ImagePart, ModelConfig, TextPart, ToolCall
from gulp_shared.llm.openai_compat import OpenAICompatProvider, _serialize

CFG = ModelConfig(
    provider="deepseek",
    model="deepseek-chat",
    api_key="sk-test",
    base_url="https://api.deepseek.com",
)


def test_serialize_system_images_and_tool_turns() -> None:
    msgs = [
        ChatMessage(
            role="user",
            content=[TextPart(text="?"), ImagePart(media_type="image/png", data_b64="aGk=")],
        ),
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[ToolCall(id="c1", name="t", arguments={"a": 1})],
        ),
        ChatMessage(role="tool", content="res", tool_call_id="c1"),
    ]
    out = _serialize("sys", msgs)
    assert out[0] == {"role": "system", "content": "sys"}
    assert out[1]["content"][1] == {
        "type": "image_url",
        "image_url": {"url": "data:image/png;base64,aGk="},
    }
    assert out[2]["tool_calls"][0]["function"] == {"name": "t", "arguments": '{"a": 1}'}
    assert out[3] == {"role": "tool", "tool_call_id": "c1", "content": "res"}


class FakeCompletions:
    def __init__(self, result: Any) -> None:
        self._result = result
        self.last_kwargs: dict[str, Any] = {}

    async def create(self, **kwargs: Any) -> Any:
        self.last_kwargs = kwargs
        return self._result


def _fake_client(result: Any) -> Any:
    return SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions(result)))


async def test_complete_json_parses_forced_function_call() -> None:
    resp = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    tool_calls=[
                        SimpleNamespace(
                            function=SimpleNamespace(name="emit", arguments='{"answer": "42"}')
                        )
                    ]
                )
            )
        ]
    )
    fake = _fake_client(resp)
    out = await OpenAICompatProvider(client=fake).complete_json(
        system="s",
        messages=[ChatMessage(role="user", content="q")],
        json_schema={"type": "object"},
        config=CFG,
    )
    assert out == {"answer": "42"}
    assert fake.chat.completions.last_kwargs["tool_choice"]["function"]["name"] == "emit"


def _chunk(
    content: str | None = None,
    tool_calls: Any = None,
    finish: str | None = None,
    usage: Any = None,
) -> Any:
    delta = SimpleNamespace(content=content, tool_calls=tool_calls)
    choice = SimpleNamespace(delta=delta, finish_reason=finish)
    return SimpleNamespace(
        choices=[choice] if (content or tool_calls or finish) else [], usage=usage
    )


async def _agen(items: list[Any]) -> Any:
    for item in items:
        yield item


async def test_stream_chat_aggregates_tool_call_fragments() -> None:
    frag1 = [
        SimpleNamespace(
            index=0, id="c1", function=SimpleNamespace(name="search", arguments='{"q":')
        )
    ]
    frag2 = [
        SimpleNamespace(index=0, id=None, function=SimpleNamespace(name=None, arguments='"x"}'))
    ]
    chunks = [
        _chunk(content="Hi"),
        _chunk(tool_calls=frag1),
        _chunk(tool_calls=frag2),
        _chunk(finish="tool_calls"),
        _chunk(usage=SimpleNamespace(prompt_tokens=7, completion_tokens=3)),
    ]
    fake = _fake_client(_agen(chunks))
    got = [
        e
        async for e in OpenAICompatProvider(client=fake).stream_chat(
            system=None, messages=[ChatMessage(role="user", content="q")], tools=None, config=CFG
        )
    ]
    assert [e.type for e in got] == ["text_delta", "tool_call", "usage", "done"]
    assert got[0].text == "Hi"  # type: ignore[union-attr]
    assert got[1].tool_call == ToolCall(id="c1", name="search", arguments={"q": "x"})  # type: ignore[union-attr]
    assert got[2].input_tokens == 7 and got[2].output_tokens == 3  # type: ignore[union-attr]
    assert got[3].stop_reason == "tool_use"  # type: ignore[union-attr]


async def test_stream_chat_plain_text_finish_stop() -> None:
    chunks = [_chunk(content="Hello"), _chunk(finish="stop")]
    fake = _fake_client(_agen(chunks))
    got = [
        e
        async for e in OpenAICompatProvider(client=fake).stream_chat(
            system="s", messages=[ChatMessage(role="user", content="q")], tools=None, config=CFG
        )
    ]
    assert [e.type for e in got] == ["text_delta", "done"]
    assert got[-1].stop_reason == "stop"  # type: ignore[union-attr]
