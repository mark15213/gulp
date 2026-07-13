"""Anthropic adapter: serialization, forced-tool JSON, stream events."""

from types import SimpleNamespace
from typing import Any

from gulp_shared.llm.anthropic_provider import AnthropicProvider, _serialize
from gulp_shared.llm.base import (
    ChatMessage,
    DoneEvent,
    ImagePart,
    ModelConfig,
    TextDelta,
    TextPart,
    ToolCall,
    ToolCallEvent,
    UsageEvent,
)

CFG = ModelConfig(provider="anthropic", model="claude-sonnet-4-6", api_key="sk-test")


def test_serialize_multimodal_and_tool_turns() -> None:
    msgs = [
        ChatMessage(
            role="user",
            content=[TextPart(text="?"), ImagePart(media_type="image/png", data_b64="aGk=")],
        ),
        ChatMessage(
            role="assistant",
            content="using tool",
            tool_calls=[ToolCall(id="c1", name="t", arguments={"a": 1})],
        ),
        ChatMessage(role="tool", content="result", tool_call_id="c1"),
    ]
    out = _serialize(msgs)
    assert out[0]["content"][1]["source"] == {
        "type": "base64",
        "media_type": "image/png",
        "data": "aGk=",
    }
    assert out[1]["content"][-1] == {"type": "tool_use", "id": "c1", "name": "t", "input": {"a": 1}}
    assert out[2] == {
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": "c1", "content": "result"}],
    }


class FakeMessages:
    def __init__(self, response: Any = None, stream: Any = None) -> None:
        self._response, self._stream = response, stream
        self.last_kwargs: dict[str, Any] = {}

    async def create(self, **kwargs: Any) -> Any:
        self.last_kwargs = kwargs
        return self._response

    def stream(self, **kwargs: Any) -> Any:
        self.last_kwargs = kwargs
        return self._stream


class FakeStream:
    """Mimics the SDK's MessageStreamManager: async context + async iterator."""

    def __init__(self, events: list[Any], final: Any) -> None:
        self._events, self._final = events, final

    async def __aenter__(self) -> "FakeStream":
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False

    def __aiter__(self) -> Any:
        async def gen() -> Any:
            for e in self._events:
                yield e

        return gen()

    async def get_final_message(self) -> Any:
        return self._final


async def test_complete_json_forces_tool_and_extracts_input() -> None:
    resp = SimpleNamespace(
        content=[SimpleNamespace(type="tool_use", id="tu1", name="emit", input={"answer": "42"})]
    )
    fake = SimpleNamespace(messages=FakeMessages(response=resp))
    out = await AnthropicProvider(client=fake).complete_json(
        system="s",
        messages=[ChatMessage(role="user", content="q")],
        json_schema={"type": "object"},
        config=CFG,
    )
    assert out == {"answer": "42"}
    assert fake.messages.last_kwargs["tool_choice"] == {"type": "tool", "name": "emit"}


async def test_stream_chat_yields_deltas_toolcalls_usage_done() -> None:
    events = [
        SimpleNamespace(
            type="content_block_delta", delta=SimpleNamespace(type="text_delta", text="Hel")
        ),
        SimpleNamespace(
            type="content_block_delta", delta=SimpleNamespace(type="text_delta", text="lo")
        ),
    ]
    final = SimpleNamespace(
        content=[SimpleNamespace(type="tool_use", id="tu1", name="search", input={"q": "x"})],
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        stop_reason="tool_use",
    )
    fake = SimpleNamespace(messages=FakeMessages(stream=FakeStream(events, final)))
    got = [
        e
        async for e in AnthropicProvider(client=fake).stream_chat(
            system=None, messages=[ChatMessage(role="user", content="q")], tools=None, config=CFG
        )
    ]
    assert [e.type for e in got] == ["text_delta", "text_delta", "tool_call", "usage", "done"]
    assert isinstance(got[0], TextDelta) and got[0].text == "Hel"
    assert isinstance(got[2], ToolCallEvent) and got[2].tool_call.name == "search"
    assert isinstance(got[3], UsageEvent) and got[3].input_tokens == 10
    assert isinstance(got[4], DoneEvent) and got[4].stop_reason == "tool_use"


async def test_stream_chat_maps_end_turn_to_stop() -> None:
    final = SimpleNamespace(content=[], usage=None, stop_reason="end_turn")
    fake = SimpleNamespace(messages=FakeMessages(stream=FakeStream([], final)))
    got = [
        e
        async for e in AnthropicProvider(client=fake).stream_chat(
            system=None, messages=[ChatMessage(role="user", content="q")], tools=None, config=CFG
        )
    ]
    assert got == [DoneEvent(stop_reason="stop")]
