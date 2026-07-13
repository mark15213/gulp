"""Provider-agnostic tool-use loop (spec 2026-07-13 §3.6). Pure logic: streams
each model turn, executes requested tools, feeds results back, and stops when
the model answers without tools or `max_iters` is exhausted."""

from collections.abc import AsyncIterator, Awaitable, Callable

from gulp_shared.llm.base import (
    ChatMessage,
    DoneEvent,
    LLMProvider,
    ModelConfig,
    StreamEvent,
    TextDelta,
    ToolCall,
    ToolCallEvent,
    ToolSpec,
)
from gulp_shared.llm.catalog import get_spec

ToolExecutor = Callable[[ToolCall], Awaitable[str]]


async def run_tool_loop(
    *,
    system: str | None,
    messages: list[ChatMessage],
    tools: list[ToolSpec],
    executor: ToolExecutor,
    config: ModelConfig,
    provider: LLMProvider | None = None,
    max_iters: int = 8,
) -> AsyncIterator[StreamEvent]:
    prov = provider if provider is not None else get_spec(config.provider).adapter
    convo = list(messages)
    for _ in range(max_iters):
        calls: list[ToolCall] = []
        text_parts: list[str] = []
        stop = "stop"
        async for ev in prov.stream_chat(system=system, messages=convo, tools=tools, config=config):
            if isinstance(ev, TextDelta):
                text_parts.append(ev.text)
                yield ev
            elif isinstance(ev, ToolCallEvent):
                calls.append(ev.tool_call)
                yield ev
            elif isinstance(ev, DoneEvent):
                stop = ev.stop_reason  # forwarded only when the loop ends
            else:
                yield ev
        if not calls:
            yield DoneEvent(stop_reason=stop)
            return
        convo.append(ChatMessage(role="assistant", content="".join(text_parts), tool_calls=calls))
        for call in calls:
            result = await executor(call)
            convo.append(ChatMessage(role="tool", content=result, tool_call_id=call.id))
    yield DoneEvent(stop_reason="max_iters")
