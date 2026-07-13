"""Contract-shape tests for the provider-neutral LLM types."""

from gulp_shared.llm.base import (
    ChatMessage,
    DoneEvent,
    ImagePart,
    LLMAuthError,
    LLMCapabilityError,
    LLMError,
    LLMNotConfiguredError,
    LLMRateLimitError,
    ModelConfig,
    TextDelta,
    TextPart,
    ToolCall,
    ToolCallEvent,
    ToolSpec,
    UsageEvent,
)


def test_error_taxonomy_subclasses_llm_error() -> None:
    for exc in (LLMNotConfiguredError, LLMAuthError, LLMRateLimitError, LLMCapabilityError):
        assert issubclass(exc, LLMError)


def test_chat_message_accepts_string_and_parts() -> None:
    plain = ChatMessage(role="user", content="hi")
    assert plain.content == "hi" and plain.tool_calls is None
    multi = ChatMessage(
        role="user",
        content=[
            TextPart(text="what is this?"),
            ImagePart(media_type="image/png", data_b64="aGk="),
        ],
    )
    assert isinstance(multi.content, list) and multi.content[1].type == "image"


def test_tool_turns_round_trip() -> None:
    call = ToolCall(id="c1", name="search", arguments={"q": "gulp"})
    assistant = ChatMessage(role="assistant", content="", tool_calls=[call])
    result = ChatMessage(role="tool", content="found it", tool_call_id="c1")
    assert assistant.tool_calls is not None and assistant.tool_calls[0].name == "search"
    assert result.tool_call_id == "c1"
    spec = ToolSpec(name="search", description="d", input_schema={"type": "object"})
    assert spec.input_schema["type"] == "object"


def test_stream_events_and_config() -> None:
    events = [
        TextDelta(text="a"),
        ToolCallEvent(tool_call=ToolCall(id="1", name="t", arguments={})),
        UsageEvent(input_tokens=1, output_tokens=2),
        DoneEvent(stop_reason="tool_use"),
    ]
    assert [e.type for e in events] == ["text_delta", "tool_call", "usage", "done"]
    cfg = ModelConfig(api_key="sk-test")  # str input coerces to SecretStr
    assert cfg.api_key.get_secret_value() == "sk-test"
    assert "sk-test" not in repr(cfg)  # never leaks in logs
